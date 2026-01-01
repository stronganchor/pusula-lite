<?php
/**
 * Plugin Name: Pusula Lite API
 * Description: REST API for the Pusula Lite desktop app (customers, sales, installments) with API key + simple record locking.
 * Version: 1.0.0
 * Author: Pusula Lite
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Pusula_Lite_API {
	const VERSION      = '1.0.0';
	const OPTION_KEY   = 'pusula_lite_api_key';
	const LOCK_TTL_SEC = 120; // seconds
	const ROLE         = 'pusula_user';

	/** @var Pusula_Lite_API|null */
	private static $instance = null;
	private $installments_has_paid_date = null;

	public static function init() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'rest_api_init', array( $this, 'register_routes' ) );
		add_action( 'admin_menu', array( $this, 'register_admin_page' ) );
		add_action( 'admin_post_pusula_export', array( $this, 'handle_export' ) );
		add_action( 'admin_post_pusula_import', array( $this, 'handle_import' ) );
		add_shortcode( 'pusula_lite_app', array( $this, 'render_shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'register_assets' ) );
	}

	// ---------------------------------------------------------------------
	// Activation
	// ---------------------------------------------------------------------
	public static function activate() {
		self::create_tables();
		self::maybe_generate_key();
		self::register_role();
	}

	private static function create_tables() {
		global $wpdb;
		$charset_collate = $wpdb->get_charset_collate();
		$prefix          = $wpdb->prefix . 'pusula_';

		require_once ABSPATH . 'wp-admin/includes/upgrade.php';

		$customers = "CREATE TABLE {$prefix}customers (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			name VARCHAR(120) NOT NULL,
			phone VARCHAR(30),
			address VARCHAR(255),
			work_address VARCHAR(255),
			notes TEXT,
			registration_date DATE NOT NULL,
			PRIMARY KEY (id),
			KEY name_idx (name)
		) {$charset_collate};";

		$sales = "CREATE TABLE {$prefix}sales (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			customer_id BIGINT UNSIGNED NOT NULL,
			date DATE NOT NULL,
			total DECIMAL(10,2) NOT NULL,
			description TEXT,
			PRIMARY KEY (id),
			KEY customer_idx (customer_id)
		) {$charset_collate};";

		$installments = "CREATE TABLE {$prefix}installments (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			sale_id BIGINT UNSIGNED NOT NULL,
			due_date DATE,
			amount DECIMAL(10,2),
			paid TINYINT(1) DEFAULT 0,
			paid_date DATE,
			PRIMARY KEY (id),
			KEY sale_idx (sale_id)
		) {$charset_collate};";

		$contacts = "CREATE TABLE {$prefix}contacts (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			customer_id BIGINT UNSIGNED NOT NULL,
			name VARCHAR(120),
			phone VARCHAR(30),
			home_address VARCHAR(255),
			work_address VARCHAR(255),
			PRIMARY KEY (id),
			KEY customer_idx (customer_id)
		) {$charset_collate};";

		$locks = "CREATE TABLE {$prefix}locks (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			record_type VARCHAR(32) NOT NULL,
			record_id BIGINT UNSIGNED NOT NULL,
			device_id VARCHAR(64) NOT NULL,
			mode VARCHAR(10) NOT NULL,
			expires_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			PRIMARY KEY (id),
			UNIQUE KEY lock_scope (record_type, record_id, device_id, mode),
			KEY record_idx (record_type, record_id),
			KEY expires_idx (expires_at)
		) {$charset_collate};";

		dbDelta( $customers );
		dbDelta( $sales );
		dbDelta( $installments );
		dbDelta( $contacts );
		dbDelta( $locks );
	}

	private static function maybe_generate_key() {
		$key = get_option( self::OPTION_KEY );
		if ( empty( $key ) ) {
			$new_key = self::generate_api_key();
			update_option( self::OPTION_KEY, $new_key );
		}
	}

	private static function generate_api_key() {
		if ( function_exists( 'random_bytes' ) ) {
			return bin2hex( random_bytes( 24 ) ); // 48 hex chars
		}
		return wp_generate_password( 48, false, false );
	}

	private static function register_role() {
		add_role(
			self::ROLE,
			'Pusula Kullanıcısı',
			array(
				'read' => true,
			)
		);
		// Ensure admins also have access
		$admin = get_role( 'administrator' );
		if ( $admin && ! $admin->has_cap( 'read' ) ) {
			$admin->add_cap( 'read' );
		}
	}

	// ---------------------------------------------------------------------
	// Admin UI
	// ---------------------------------------------------------------------
	public function register_admin_page() {
		add_options_page(
			'Pusula Lite API',
			'Pusula API',
			'manage_options',
			'pusula-lite-api',
			array( $this, 'render_settings_page' )
		);
		add_options_page(
			'Pusula Backup',
			'Pusula Backup',
			'manage_options',
			'pusula-lite-backup',
			array( $this, 'render_backup_page' )
		);
	}

	public function render_settings_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		if ( isset( $_POST['pusula_regen_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['pusula_regen_nonce'] ) ), 'pusula_regen_key' ) ) {
			update_option( self::OPTION_KEY, self::generate_api_key() );
			echo '<div class="notice notice-success is-dismissible"><p>API key regenerated.</p></div>';
		}

		$key = get_option( self::OPTION_KEY );
		?>
		<div class="wrap">
			<h1>Pusula Lite API</h1>
			<p>Provide the API key below to the desktop client. Keep it secret.</p>
			<p><strong>API Key:</strong></p>
			<code style="font-size:14px;"><?php echo esc_html( $key ); ?></code>
			<form method="post" style="margin-top:16px;">
				<?php wp_nonce_field( 'pusula_regen_key', 'pusula_regen_nonce' ); ?>
				<button type="submit" class="button button-secondary">Regenerate Key</button>
			</form>
		</div>
		<?php
	}

	// ---------------------------------------------------------------------
	// Backup / Import
	// ---------------------------------------------------------------------
	private function get_backup_page_url() {
		return admin_url( 'options-general.php?page=pusula-lite-backup' );
	}

	public function render_backup_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		$status  = isset( $_GET['pusula_import'] ) ? sanitize_key( wp_unslash( $_GET['pusula_import'] ) ) : '';
		$message = isset( $_GET['pusula_message'] ) ? sanitize_text_field( wp_unslash( $_GET['pusula_message'] ) ) : '';
		$notice = '';
		$notice_class = '';

		if ( 'success' === $status ) {
			$notice = $message ? $message : 'Import completed. Existing data was replaced.';
			$notice_class = 'notice-success';
		} elseif ( 'error' === $status ) {
			$notice = $message ? $message : 'Import failed. Please check the file and try again.';
			$notice_class = 'notice-error';
		}
		?>
		<div class="wrap">
			<h1>Pusula Backup</h1>
			<?php if ( $notice ) : ?>
				<div class="notice <?php echo esc_attr( $notice_class ); ?> is-dismissible"><p><?php echo esc_html( $notice ); ?></p></div>
			<?php endif; ?>

			<h2>Export</h2>
			<p>Download a JSON backup of all Pusula tables. Use this file to restore or migrate data to another site.</p>
			<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<?php wp_nonce_field( 'pusula_export', 'pusula_export_nonce' ); ?>
				<input type="hidden" name="action" value="pusula_export">
				<button type="submit" class="button button-secondary">Download Export</button>
			</form>

			<hr />

			<h2>Import</h2>
			<p><strong>Warning:</strong> Importing will delete all existing Pusula data on this site and replace it with the file contents.</p>
			<form method="post" enctype="multipart/form-data" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<?php wp_nonce_field( 'pusula_import', 'pusula_import_nonce' ); ?>
				<input type="hidden" name="action" value="pusula_import">
				<input type="file" name="pusula_import_file" accept=".json,application/json" required>
				<p style="margin-top:12px;">
					<button type="submit" class="button button-primary" onclick="return confirm('This will erase all existing Pusula data and replace it. Continue?');">Import and Replace Data</button>
				</p>
			</form>
		</div>
		<?php
	}

	public function handle_export() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( 'Insufficient permissions.' );
		}

		check_admin_referer( 'pusula_export', 'pusula_export_nonce' );

		$payload = $this->build_export_payload();
		$json = wp_json_encode( $payload );
		if ( false === $json ) {
			wp_die( 'Export failed. Please try again.' );
		}

		nocache_headers();
		$filename = 'pusula-backup-' . current_time( 'Ymd-His' ) . '.json';
		header( 'Content-Type: application/json; charset=' . get_option( 'blog_charset' ) );
		header( 'Content-Disposition: attachment; filename="' . $filename . '"' );
		echo $json;
		exit;
	}

	public function handle_import() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( 'Insufficient permissions.' );
		}

		check_admin_referer( 'pusula_import', 'pusula_import_nonce' );

		if ( empty( $_FILES['pusula_import_file'] ) ) {
			$this->redirect_with_import_notice( 'error', 'No file was uploaded.' );
		}

		$file = $_FILES['pusula_import_file'];
		if ( ! empty( $file['error'] ) ) {
			$message = UPLOAD_ERR_NO_FILE === (int) $file['error'] ? 'No file was uploaded.' : 'Upload failed. Please try again.';
			$this->redirect_with_import_notice( 'error', $message );
		}

		if ( empty( $file['tmp_name'] ) || ! is_uploaded_file( $file['tmp_name'] ) ) {
			$this->redirect_with_import_notice( 'error', 'Upload failed. Please try again.' );
		}

		$json = file_get_contents( $file['tmp_name'] );
		if ( false === $json ) {
			$this->redirect_with_import_notice( 'error', 'Could not read the uploaded file.' );
		}

		$payload = $this->parse_import_payload( $json );
		if ( is_wp_error( $payload ) ) {
			$this->redirect_with_import_notice( 'error', $payload->get_error_message() );
		}

		$result = $this->import_payload( $payload );
		if ( is_wp_error( $result ) ) {
			$this->redirect_with_import_notice( 'error', $result->get_error_message() );
		}

		$this->redirect_with_import_notice( 'success', 'Import completed. Existing data was replaced.' );
	}

	private function redirect_with_import_notice( $status, $message ) {
		$url = add_query_arg(
			array(
				'pusula_import'  => $status,
				'pusula_message' => $message,
			),
			$this->get_backup_page_url()
		);
		wp_safe_redirect( $url );
		exit;
	}

	private function build_export_payload() {
		global $wpdb;

		$this->purge_expired_locks();
		$tables = $this->get_export_tables();
		$data = array();

		foreach ( $tables as $key => $table ) {
			$data[ $key ] = $wpdb->get_results( "SELECT * FROM {$table}", ARRAY_A );
		}

		return array(
			'version'     => self::VERSION,
			'exported_at' => current_time( 'mysql' ),
			'meta'        => array(
				'installments_has_paid_date' => $this->installments_has_paid_date(),
			),
			'tables'      => $data,
		);
	}

	private function parse_import_payload( $json ) {
		$data = json_decode( $json, true );
		if ( ! is_array( $data ) ) {
			return new WP_Error( 'invalid_json', 'Invalid JSON file.' );
		}

		$tables = isset( $data['tables'] ) && is_array( $data['tables'] ) ? $data['tables'] : $data;
		$allowed = array( 'customers', 'sales', 'installments', 'contacts', 'locks' );
		$normalized = array();

		foreach ( $allowed as $key ) {
			$normalized[ $key ] = isset( $tables[ $key ] ) && is_array( $tables[ $key ] ) ? $tables[ $key ] : array();
		}

		$meta = isset( $data['meta'] ) && is_array( $data['meta'] ) ? $data['meta'] : array();

		return array(
			'tables' => $normalized,
			'meta'   => $meta,
		);
	}

	private function import_payload( array $payload ) {
		global $wpdb;
		$tables = $payload['tables'];
		$meta = $payload['meta'];
		$table_map = $this->get_export_tables();

		$needs_paid_date = ! empty( $meta['installments_has_paid_date'] );
		if ( ! $needs_paid_date && ! empty( $tables['installments'] ) ) {
			foreach ( $tables['installments'] as $row ) {
				if ( is_array( $row ) && array_key_exists( 'paid_date', $row ) ) {
					$needs_paid_date = true;
					break;
				}
			}
		}
		if ( $needs_paid_date ) {
			$this->ensure_installments_paid_date_column();
		}

		$use_transaction = false;
		if ( false !== $wpdb->query( 'START TRANSACTION' ) ) {
			$use_transaction = true;
		}

		$wipe_order = array( 'installments', 'sales', 'contacts', 'customers', 'locks' );
		foreach ( $wipe_order as $key ) {
			$result = $this->clear_table( $table_map[ $key ] );
			if ( is_wp_error( $result ) ) {
				if ( $use_transaction ) {
					$wpdb->query( 'ROLLBACK' );
				}
				return $result;
			}
		}

		$insert_order = array( 'customers', 'sales', 'installments', 'contacts', 'locks' );
		foreach ( $insert_order as $key ) {
			$result = $this->insert_table_rows( $table_map[ $key ], $tables[ $key ] );
			if ( is_wp_error( $result ) ) {
				if ( $use_transaction ) {
					$wpdb->query( 'ROLLBACK' );
				}
				return $result;
			}
		}

		if ( $use_transaction ) {
			$wpdb->query( 'COMMIT' );
		}

		return true;
	}

	private function clear_table( $table ) {
		global $wpdb;
		$result = $wpdb->query( "DELETE FROM {$table}" );
		if ( false === $result ) {
			return new WP_Error( 'delete_failed', 'Failed to clear table ' . $table . '.' );
		}
		return true;
	}

	private function insert_table_rows( $table, array $rows ) {
		global $wpdb;
		if ( empty( $rows ) ) {
			return true;
		}

		$columns = $this->get_table_columns( $table );
		if ( empty( $columns ) ) {
			return new WP_Error( 'missing_table', 'Table not found: ' . $table . '.' );
		}

		$column_lookup = array_flip( $columns );
		foreach ( $rows as $row ) {
			if ( ! is_array( $row ) ) {
				continue;
			}

			$data = array();
			foreach ( $row as $column => $value ) {
				if ( isset( $column_lookup[ $column ] ) ) {
					$data[ $column ] = $value;
				}
			}

			if ( empty( $data ) ) {
				continue;
			}

			$inserted = $wpdb->insert( $table, $data );
			if ( false === $inserted ) {
				return new WP_Error( 'insert_failed', 'Import failed while inserting data into ' . $table . '.' );
			}
		}

		return true;
	}

	private function get_table_columns( $table ) {
		global $wpdb;
		$columns = $wpdb->get_col( "SHOW COLUMNS FROM {$table}", 0 );
		return $columns ? $columns : array();
	}

	private function get_export_tables() {
		return array(
			'customers'    => $this->get_table( 'customers' ),
			'sales'        => $this->get_table( 'sales' ),
			'installments' => $this->get_table( 'installments' ),
			'contacts'     => $this->get_table( 'contacts' ),
			'locks'        => $this->get_table( 'locks' ),
		);
	}

	// ---------------------------------------------------------------------
	// Shortcode / Assets
	// ---------------------------------------------------------------------
	public function register_assets() {
		$base_url = plugins_url( '', __FILE__ );
		$css_path = plugin_dir_path( __FILE__ ) . 'assets/pusula-app.css';
		$js_path  = plugin_dir_path( __FILE__ ) . 'assets/pusula-app.js';
		$css_ver  = file_exists( $css_path ) ? filemtime( $css_path ) : self::VERSION;
		$js_ver   = file_exists( $js_path ) ? filemtime( $js_path ) : self::VERSION;
		wp_register_style(
			'pusula-lite-app',
			$base_url . '/assets/pusula-app.css',
			array(),
			$css_ver
		);
		wp_register_script(
			'pusula-lite-app',
			$base_url . '/assets/pusula-app.js',
			array(),
			$js_ver,
			true
		);
	}

	public function render_shortcode() {
		if ( ! is_user_logged_in() ) {
			wp_enqueue_style( 'pusula-lite-app' );

			$error    = '';
			$redirect = home_url( wp_unslash( $_SERVER['REQUEST_URI'] ) );

			if ( isset( $_POST['pusula_login'] ) ) {
				$nonce_ok = isset( $_POST['pusula_login_nonce'] ) && wp_verify_nonce(
					sanitize_text_field( wp_unslash( $_POST['pusula_login_nonce'] ) ),
					'pusula_login'
				);

				if ( ! $nonce_ok ) {
					$error = 'Güvenlik doğrulaması başarısız. Lütfen sayfayı yenileyip tekrar deneyin.';
				} else {
					$user_login = isset( $_POST['log'] ) ? sanitize_user( wp_unslash( $_POST['log'] ) ) : '';
					$user_pass  = isset( $_POST['pwd'] ) ? (string) wp_unslash( $_POST['pwd'] ) : '';
					$remember   = ! empty( $_POST['rememberme'] );

					$user = wp_signon(
						array(
							'user_login'    => $user_login,
							'user_password' => $user_pass,
							'remember'      => $remember,
						),
						is_ssl()
					);

					if ( is_wp_error( $user ) ) {
						$code = $user->get_error_code();
						switch ( $code ) {
							case 'empty_username':
								$error = 'Kullanıcı adı zorunludur.';
								break;
							case 'empty_password':
								$error = 'Şifre zorunludur.';
								break;
							case 'invalid_username':
								$error = 'Kullanıcı adı bulunamadı.';
								break;
							case 'incorrect_password':
								$error = 'Şifre hatalı.';
								break;
							default:
								$error = 'Giriş yapılamadı. Lütfen bilgilerinizi kontrol edin.';
								break;
						}
					} else {
						wp_safe_redirect( $redirect );
						exit;
					}
				}
			}

			ob_start();
			?>
			<div class="pusula-app pusula-login">
				<div class="pusula-login-card">
					<div class="pusula-login-title">Pusula</div>
					<div class="pusula-login-subtitle">Devam etmek için giriş yapın.</div>
					<?php if ( $error ) : ?>
						<div class="pusula-login-error"><?php echo esc_html( $error ); ?></div>
					<?php endif; ?>
					<form method="post" autocomplete="on">
						<?php echo wp_nonce_field( 'pusula_login', 'pusula_login_nonce', true, false ); ?>
						<input type="hidden" name="redirect_to" value="<?php echo esc_url( $redirect ); ?>">
						<label class="pusula-login-field">
							<span>Kullanıcı adı</span>
							<input type="text" name="log" autocomplete="username" required>
						</label>
						<label class="pusula-login-field">
							<span>Şifre</span>
							<input type="password" name="pwd" autocomplete="current-password" required>
						</label>
						<label class="pusula-login-remember">
							<input type="checkbox" name="rememberme" value="forever">
							<span>Beni hatırla</span>
						</label>
						<div class="pusula-actions pusula-login-actions">
							<button type="submit" name="pusula_login" value="1">GİRİŞ YAP</button>
						</div>
					</form>
				</div>
			</div>
			<?php
			return ob_get_clean();
		}
		$current = wp_get_current_user();
		if ( ! in_array( self::ROLE, (array) $current->roles, true ) && ! current_user_can( 'administrator' ) ) {
			wp_enqueue_style( 'pusula-lite-app' );
			return '<div class="pusula-app pusula-login"><div class="pusula-login-card"><div class="pusula-login-error">Bu sayfayı görme yetkiniz yok.</div></div></div>';
		}

		wp_enqueue_style( 'pusula-lite-app' );
		wp_enqueue_script( 'pusula-lite-app' );

		wp_localize_script(
			'pusula-lite-app',
			'PusulaApp',
			array(
				'apiBase' => esc_url_raw( rest_url( 'pusula/v1' ) ),
				'nonce'   => wp_create_nonce( 'wp_rest' ),
			)
		);

		// Hide admin bar only for this view to prevent extra page scroll
		add_filter(
			'show_admin_bar',
			function() {
				return false;
			},
			99
		);

		ob_start();
		?>
		<div id="pusula-lite-app" class="pusula-app">
			<div class="pusula-header">
				<div class="pusula-title-tabs">
					<div class="pusula-tabs">
						<button class="active" data-tab="search">MÜŞTERİ ARAMA</button>
						<button data-tab="add">MÜŞTERİ BİLGİLERİ</button>
						<button data-tab="sale">SATIŞ KAYDET</button>
						<button data-tab="detail">TAKSİTLİ SATIŞ KAYIT BİLGİSİ</button>
						<button data-tab="report">GÜNLÜK SATIŞ RAPORU</button>
						<button data-tab="expected">BEKLENEN ÖDEMELER</button>
					</div>
				</div>
				<div class="pusula-status" id="pusula-status"></div>
			</div>
			<div class="pusula-tab-content" id="pusula-tab-search"></div>
			<div class="pusula-tab-content" id="pusula-tab-add" style="display:none"></div>
			<div class="pusula-tab-content" id="pusula-tab-sale" style="display:none"></div>
			<div class="pusula-tab-content" id="pusula-tab-detail" style="display:none"></div>
			<div class="pusula-tab-content" id="pusula-tab-report" style="display:none"></div>
			<div class="pusula-tab-content" id="pusula-tab-expected" style="display:none"></div>
		</div>
		<?php
		return ob_get_clean();
	}

	// ---------------------------------------------------------------------
	// Routing / Auth
	// ---------------------------------------------------------------------
	public function register_routes() {
		$namespace = 'pusula/v1';

		// Customers
		register_rest_route(
			$namespace,
			'/customers',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_customers' ),
				'permission_callback' => array( $this, 'permission_callback' ),
				'args'                => array(
					'search' => array(
						'sanitize_callback' => 'sanitize_text_field',
					),
					'with'   => array(
						'sanitize_callback' => 'sanitize_text_field',
					),
					'id'     => array( 'sanitize_callback' => 'absint' ),
					'name'   => array( 'sanitize_callback' => 'sanitize_text_field' ),
					'phone'  => array( 'sanitize_callback' => 'sanitize_text_field' ),
					'address'=> array( 'sanitize_callback' => 'sanitize_text_field' ),
					'limit'  => array( 'sanitize_callback' => 'absint' ),
					'offset' => array( 'sanitize_callback' => 'absint' ),
				),
			)
		);

		// Next customer id (lowest available)
		register_rest_route(
			$namespace,
			'/customers/next-id',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_next_customer_id' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/customers',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'create_customer' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/customers/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_customer' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/customers/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::EDITABLE,
				'callback'            => array( $this, 'update_customer' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);
		register_rest_route(
			$namespace,
			'/customers/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::DELETABLE,
				'callback'            => array( $this, 'delete_customer' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		// Contacts
		register_rest_route(
			$namespace,
			'/customers/(?P<id>\d+)/contacts',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_contacts' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/customers/(?P<id>\d+)/contacts',
			array(
				'methods'             => WP_REST_Server::EDITABLE,
				'callback'            => array( $this, 'replace_contacts' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		// Sales
		register_rest_route(
			$namespace,
			'/sales',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_sales' ),
				'permission_callback' => array( $this, 'permission_callback' ),
				'args'                => array(
					'with' => array(
						'sanitize_callback' => 'sanitize_text_field',
					),
				),
			)
		);

		register_rest_route(
			$namespace,
			'/sales',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'create_sale' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/sales/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_sale' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/sales/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::EDITABLE,
				'callback'            => array( $this, 'update_sale' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/sales/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::DELETABLE,
				'callback'            => array( $this, 'delete_sale' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		// Expected payments (beklenen ödemeler)
		register_rest_route(
			$namespace,
			'/expected-payments',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_expected_payments' ),
				'permission_callback' => array( $this, 'permission_callback' ),
				'args'                => array(
					'start' => array( 'sanitize_callback' => 'sanitize_text_field' ),
					'end'   => array( 'sanitize_callback' => 'sanitize_text_field' ),
				),
			)
		);

		// Installments (taksit)
		register_rest_route(
			$namespace,
			'/installments',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_installments' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/installments',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'create_installment' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/installments/(?P<id>\d+)',
			array(
				'methods'             => WP_REST_Server::EDITABLE,
				'callback'            => array( $this, 'update_installment' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		// Locks
		register_rest_route(
			$namespace,
			'/locks',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'acquire_lock' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/locks/release',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'release_lock' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);
	}

	public function permission_callback( WP_REST_Request $request ) {
		// Allow authenticated WP users with pusula role or admins
		if ( is_user_logged_in() ) {
			$user = wp_get_current_user();
			if ( in_array( self::ROLE, (array) $user->roles, true ) || current_user_can( 'manage_options' ) ) {
				return true;
			}
		}
		// Fallback to API key header (for desktop app)
		$provided = $request->get_header( 'x-api-key' );
		$stored   = get_option( self::OPTION_KEY );
		if ( $stored && $provided && hash_equals( $stored, $provided ) ) {
			return true;
		}
		return new WP_Error( 'pusula_forbidden', 'Geçersiz veya eksik API anahtarı.', array( 'status' => 401 ) );
	}

	private function get_table( $suffix ) {
		global $wpdb;
		return $wpdb->prefix . 'pusula_' . $suffix;
	}

	private function installments_has_paid_date() {
		if ( null !== $this->installments_has_paid_date ) {
			return $this->installments_has_paid_date;
		}
		global $wpdb;
		$table  = $this->get_table( 'installments' );
		$column = $wpdb->get_var( $wpdb->prepare( "SHOW COLUMNS FROM {$table} LIKE %s", 'paid_date' ) );
		$this->installments_has_paid_date = ! empty( $column );
		return $this->installments_has_paid_date;
	}

	private function ensure_installments_paid_date_column() {
		if ( $this->installments_has_paid_date() ) {
			return true;
		}
		global $wpdb;
		$table = $this->get_table( 'installments' );
		$wpdb->query( "ALTER TABLE {$table} ADD COLUMN paid_date DATE NULL" );
		if ( $wpdb->last_error ) {
			$this->installments_has_paid_date = null;
			return $this->installments_has_paid_date();
		}
		$this->installments_has_paid_date = true;
		return true;
	}

	// ---------------------------------------------------------------------
	// Customers
	// ---------------------------------------------------------------------
	private function get_lowest_available_customer_id() {
		global $wpdb;
		$table = $this->get_table( 'customers' );
		$has_one = (int) $wpdb->get_var(
			$wpdb->prepare( "SELECT 1 FROM {$table} WHERE id = %d LIMIT 1", 1 )
		);
		if ( ! $has_one ) {
			return 1;
		}
		$next = (int) $wpdb->get_var(
			"SELECT MIN(t1.id + 1)
			 FROM {$table} t1
			 LEFT JOIN {$table} t2 ON t1.id + 1 = t2.id
			 WHERE t2.id IS NULL"
		);
		return $next > 0 ? $next : 1;
	}

	public function get_next_customer_id( WP_REST_Request $request ) {
		$next_id = $this->get_lowest_available_customer_id();
		return rest_ensure_response(
			array(
				'next_id' => $next_id,
			)
		);
	}

	public function get_customers( WP_REST_Request $request ) {
		global $wpdb;
		$table  = $this->get_table( 'customers' );
		$search = $request->get_param( 'search' );
		$with   = $request->get_param( 'with' );
		$with_contacts = $with && false !== strpos( $with, 'contacts' );
		$with_late = $with && false !== strpos( $with, 'late_unpaid' );
		$id     = absint( $request->get_param( 'id' ) );
		$name   = $request->get_param( 'name' );
		$phone  = $request->get_param( 'phone' );
		$addr   = $request->get_param( 'address' );
		$limit  = $request->get_param( 'limit' ) ? absint( $request->get_param( 'limit' ) ) : 100;
		$offset = $request->get_param( 'offset' ) ? absint( $request->get_param( 'offset' ) ) : 0;
		$limit  = max( 1, min( 500, $limit ) ); // cap to avoid huge dumps

		$where  = array();
		$params = array();

		if ( $id ) {
			$where[]  = 'id = %d';
			$params[] = $id;
		}

		if ( $search ) {
			$like = '%' . $wpdb->esc_like( $search ) . '%';
			$where[]  = '(name LIKE %s OR phone LIKE %s OR address LIKE %s OR work_address LIKE %s)';
			$params[] = $like;
			$params[] = $like;
			$params[] = $like;
			$params[] = $like;
		}
		if ( $name ) {
			$like = '%' . $wpdb->esc_like( $name ) . '%';
			$where[]  = 'name LIKE %s';
			$params[] = $like;
		}
		if ( $phone ) {
			$like = '%' . $wpdb->esc_like( $phone ) . '%';
			$where[]  = 'phone LIKE %s';
			$params[] = $like;
		}
		if ( $addr ) {
			$like = '%' . $wpdb->esc_like( $addr ) . '%';
			$where[]  = '(address LIKE %s OR work_address LIKE %s)';
			$params[] = $like;
			$params[] = $like;
		}

		if ( empty( $where ) ) {
			$where[] = '1=1';
		}

		$sql = 'SELECT * FROM ' . $table . ' WHERE ' . implode( ' AND ', $where ) . ' ORDER BY registration_date DESC, id DESC';
		$sql .= $wpdb->prepare( ' LIMIT %d OFFSET %d', $limit, $offset );
		if ( $params ) {
			$sql = $wpdb->prepare( $sql, $params );
		}

		$rows = $wpdb->get_results( $sql, ARRAY_A );
		if ( $with_contacts && $rows ) {
			$ids = wp_list_pluck( $rows, 'id' );
			$contacts = $this->get_contacts_for_customers( $ids );
			foreach ( $rows as &$row ) {
				$row['contacts'] = $contacts[ $row['id'] ] ?? array();
			}
			unset( $row );
		}
		if ( $with_late && $rows ) {
			$ids = array_map( 'intval', wp_list_pluck( $rows, 'id' ) );
			$ids = array_values( array_filter( $ids ) );
			$late_lookup = array();
			if ( $ids ) {
				$sales_table = $this->get_table( 'sales' );
				$inst_table  = $this->get_table( 'installments' );
				$today       = current_time( 'Y-m-d' );
				$placeholders = implode( ',', array_fill( 0, count( $ids ), '%d' ) );
				$params = array_merge( $ids, array( $today ) );
				$late_ids = $wpdb->get_col(
					$wpdb->prepare(
						"SELECT DISTINCT s.customer_id
						 FROM {$sales_table} s
						 INNER JOIN {$inst_table} i ON i.sale_id = s.id
						 WHERE s.customer_id IN ({$placeholders})
						   AND i.paid = 0
						   AND i.due_date IS NOT NULL
						   AND i.due_date < %s",
						$params
					)
				);
				if ( $late_ids ) {
					$late_lookup = array_fill_keys( array_map( 'intval', $late_ids ), true );
				}
			}
			foreach ( $rows as &$row ) {
				$row['late_unpaid'] = ! empty( $late_lookup[ (int) $row['id'] ] ) ? 1 : 0;
			}
			unset( $row );
		}
		return rest_ensure_response( $rows );
	}

	public function get_customer( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'customers' );
		$id    = absint( $request['id'] );
		$row   = $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$table} WHERE id = %d", $id ), ARRAY_A );

		if ( ! $row ) {
			return new WP_Error( 'not_found', 'Müşteri bulunamadı.', array( 'status' => 404 ) );
		}

		$row['contacts'] = $this->get_contacts( $request )->get_data();

		return rest_ensure_response( $row );
	}

	public function create_customer( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'customers' );

		$name = sanitize_text_field( $request->get_param( 'name' ) );
		if ( empty( $name ) ) {
			return new WP_Error( 'missing_name', 'Müşteri adı zorunludur.', array( 'status' => 400 ) );
		}

		$requested_id = absint( $request->get_param( 'id' ) );
		if ( $requested_id ) {
			$exists = (int) $wpdb->get_var( $wpdb->prepare( "SELECT id FROM {$table} WHERE id = %d", $requested_id ) );
			if ( $exists ) {
				$requested_id = 0;
			}
		}
		$customer_id = $requested_id ? $requested_id : $this->get_lowest_available_customer_id();

		$data = array(
			'id'                => $customer_id,
			'name'              => $name,
			'phone'             => sanitize_text_field( $request->get_param( 'phone' ) ),
			'address'           => sanitize_text_field( $request->get_param( 'address' ) ),
			'work_address'      => sanitize_text_field( $request->get_param( 'work_address' ) ),
			'notes'             => sanitize_textarea_field( $request->get_param( 'notes' ) ),
			'registration_date' => $request->get_param( 'registration_date' ) ? sanitize_text_field( $request->get_param( 'registration_date' ) ) : current_time( 'Y-m-d' ),
		);

		$inserted = $wpdb->insert(
			$table,
			$data,
			array( '%d', '%s', '%s', '%s', '%s', '%s', '%s' )
		);
		if ( false === $inserted ) {
			return new WP_Error( 'insert_failed', 'Müşteri kaydı oluşturulamadı.', array( 'status' => 500 ) );
		}

		$contacts = $request->get_param( 'contacts' );
		if ( $contacts ) {
			$this->store_contacts( $customer_id, $contacts );
		}

		return rest_ensure_response(
			array(
				'id' => $customer_id,
			)
		);
	}

	public function update_customer( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'customers' );
		$id    = absint( $request['id'] );

		$existing = $wpdb->get_var( $wpdb->prepare( "SELECT id FROM {$table} WHERE id = %d", $id ) );
		if ( ! $existing ) {
			return new WP_Error( 'not_found', 'Müşteri bulunamadı.', array( 'status' => 404 ) );
		}

		$data = array(
			'name'         => sanitize_text_field( $request->get_param( 'name' ) ),
			'phone'        => sanitize_text_field( $request->get_param( 'phone' ) ),
			'address'      => sanitize_text_field( $request->get_param( 'address' ) ),
			'work_address' => sanitize_text_field( $request->get_param( 'work_address' ) ),
			'notes'        => sanitize_textarea_field( $request->get_param( 'notes' ) ),
		);

		$wpdb->update(
			$table,
			$data,
			array( 'id' => $id ),
			array( '%s', '%s', '%s', '%s', '%s' ),
			array( '%d' )
		);

		$contacts = $request->get_param( 'contacts' );
		if ( null !== $contacts ) {
			$this->store_contacts( $id, $contacts );
		}

		return rest_ensure_response( array( 'updated' => true ) );
	}

	public function delete_customer( WP_REST_Request $request ) {
		global $wpdb;
		$id          = absint( $request['id'] );
		$cust_table  = $this->get_table( 'customers' );
		$sales_table = $this->get_table( 'sales' );
		$inst_table  = $this->get_table( 'installments' );
		$contact_tbl = $this->get_table( 'contacts' );

		// delete installments for this customer's sales
		$sale_ids = $wpdb->get_col( $wpdb->prepare( "SELECT id FROM {$sales_table} WHERE customer_id = %d", $id ) );
		if ( $sale_ids ) {
			foreach ( $sale_ids as $sid ) {
				$wpdb->delete( $inst_table, array( 'sale_id' => $sid ), array( '%d' ) );
			}
		}

		$wpdb->delete( $sales_table, array( 'customer_id' => $id ), array( '%d' ) );
		$wpdb->delete( $contact_tbl, array( 'customer_id' => $id ), array( '%d' ) );
		$wpdb->delete( $cust_table, array( 'id' => $id ), array( '%d' ) );

		return rest_ensure_response( array( 'deleted' => true ) );
	}

	private function get_contacts_for_customers( array $customer_ids ) {
		global $wpdb;
		if ( empty( $customer_ids ) ) {
			return array();
		}
		$table = $this->get_table( 'contacts' );
		$placeholders = implode( ',', array_fill( 0, count( $customer_ids ), '%d' ) );
		$sql = $wpdb->prepare( "SELECT * FROM {$table} WHERE customer_id IN ($placeholders) ORDER BY id ASC", $customer_ids );
		$rows = $wpdb->get_results( $sql, ARRAY_A );
		$grouped = array();
		foreach ( $rows as $row ) {
			$cid = (int) $row['customer_id'];
			if ( ! isset( $grouped[ $cid ] ) ) {
				$grouped[ $cid ] = array();
			}
			$grouped[ $cid ][] = $row;
		}
		return $grouped;
	}

	private function store_contacts( $customer_id, $contacts ) {
		global $wpdb;
		$table = $this->get_table( 'contacts' );
		$wpdb->delete( $table, array( 'customer_id' => $customer_id ), array( '%d' ) );

		if ( empty( $contacts ) || ! is_array( $contacts ) ) {
			return;
		}

		foreach ( $contacts as $contact ) {
			$wpdb->insert(
				$table,
				array(
					'customer_id'   => $customer_id,
					'name'          => isset( $contact['name'] ) ? sanitize_text_field( $contact['name'] ) : '',
					'phone'         => isset( $contact['phone'] ) ? sanitize_text_field( $contact['phone'] ) : '',
					'home_address'  => isset( $contact['home_address'] ) ? sanitize_text_field( $contact['home_address'] ) : '',
					'work_address'  => isset( $contact['work_address'] ) ? sanitize_text_field( $contact['work_address'] ) : '',
				),
				array( '%d', '%s', '%s', '%s', '%s' )
			);
		}
	}

	public function get_contacts( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'contacts' );
		$id    = absint( $request['id'] );

		$rows = $wpdb->get_results(
			$wpdb->prepare( "SELECT * FROM {$table} WHERE customer_id = %d ORDER BY id ASC", $id ),
			ARRAY_A
		);

		return rest_ensure_response( $rows );
	}

	public function replace_contacts( WP_REST_Request $request ) {
		$id       = absint( $request['id'] );
		$contacts = $request->get_json_params();

		$this->store_contacts( $id, $contacts );

		return rest_ensure_response( array( 'saved' => true ) );
	}

	// ---------------------------------------------------------------------
	// Sales
	// ---------------------------------------------------------------------
	public function get_sales( WP_REST_Request $request ) {
		global $wpdb;
		$table      = $this->get_table( 'sales' );
		$cust_table = $this->get_table( 'customers' );
		$inst_table = $this->get_table( 'installments' );

		$customer_id = absint( $request->get_param( 'customer_id' ) );
		$start       = $request->get_param( 'start' );
		$end         = $request->get_param( 'end' );
		$with        = $request->get_param( 'with' );
		$with_inst   = $with && false !== strpos( $with, 'installments' );

		$where  = array( '1=1' );
		$params = array();

		if ( $customer_id ) {
			$where[]  = 's.customer_id = %d';
			$params[] = $customer_id;
		}

		if ( $start ) {
			$where[]  = 's.date >= %s';
			$params[] = sanitize_text_field( $start );
		}
		if ( $end ) {
			$where[]  = 's.date <= %s';
			$params[] = sanitize_text_field( $end );
		}

		$sql = "SELECT s.*, c.name AS customer_name
			FROM {$table} s
			LEFT JOIN {$cust_table} c ON c.id = s.customer_id
			WHERE " . implode( ' AND ', $where ) . '
			ORDER BY s.date DESC, s.id DESC';

		if ( $params ) {
			$sql = $wpdb->prepare( $sql, $params );
		}

		$rows = $wpdb->get_results( $sql, ARRAY_A );

		if ( $with_inst && $rows ) {
			$sale_ids = wp_list_pluck( $rows, 'id' );
			$placeholders = implode( ',', array_fill( 0, count( $sale_ids ), '%d' ) );
			$inst_sql = $wpdb->prepare( "SELECT * FROM {$inst_table} WHERE sale_id IN ($placeholders) ORDER BY due_date ASC, id ASC", $sale_ids );
			$inst_rows = $wpdb->get_results( $inst_sql, ARRAY_A );
			$grouped = array();
			foreach ( $inst_rows as $inst ) {
				$inst['paid'] = (int) $inst['paid'];
				$sid = (int) $inst['sale_id'];
				if ( ! isset( $grouped[ $sid ] ) ) {
					$grouped[ $sid ] = array();
				}
				$grouped[ $sid ][] = $inst;
			}
			foreach ( $rows as &$row ) {
				$row['installments'] = $grouped[ $row['id'] ] ?? array();
			}
			unset( $row );
		}

		return rest_ensure_response( $rows );
	}

	public function get_expected_payments( WP_REST_Request $request ) {
		global $wpdb;
		$sales_table = $this->get_table( 'sales' );
		$inst_table  = $this->get_table( 'installments' );
		$cust_table  = $this->get_table( 'customers' );

		$start = $request->get_param( 'start' );
		$end   = $request->get_param( 'end' );

		$today         = current_time( 'Y-m-d' );
		$has_paid_date = $this->ensure_installments_paid_date_column();
		if ( $has_paid_date ) {
			$where            = array( 'i.due_date IS NOT NULL', '(COALESCE(i.paid, 0) = 0 OR (i.paid = 1 AND i.paid_date = %s))' );
			$params           = array( $today );
			$paid_date_select = 'i.paid_date';
		} else {
			$where            = array( 'i.due_date IS NOT NULL', 'COALESCE(i.paid, 0) = 0' );
			$params           = array();
			$paid_date_select = 'NULL AS paid_date';
		}

		if ( $start ) {
			$where[]  = 'i.due_date >= %s';
			$params[] = sanitize_text_field( $start );
		}
		if ( $end ) {
			$where[]  = 'i.due_date <= %s';
			$params[] = sanitize_text_field( $end );
		}

		$sql = "SELECT
				i.id AS installment_id,
				i.due_date,
				i.amount,
				i.paid,
				{$paid_date_select},
				s.id AS sale_id,
				s.date AS sale_date,
				s.total AS sale_total,
				s.description AS sale_description,
				c.id AS customer_id,
				c.name AS customer_name,
				c.phone AS customer_phone,
				c.address AS customer_address,
				c.work_address AS customer_work_address
			FROM {$inst_table} i
			INNER JOIN {$sales_table} s ON s.id = i.sale_id
			INNER JOIN {$cust_table} c ON c.id = s.customer_id
			WHERE " . implode( ' AND ', $where ) . '
			ORDER BY i.due_date ASC, i.id ASC';

		if ( $params ) {
			$sql = $wpdb->prepare( $sql, $params );
		}

		$rows = $wpdb->get_results( $sql, ARRAY_A );
		if ( $rows ) {
			foreach ( $rows as &$row ) {
				$row['paid'] = (int) $row['paid'];
			}
			unset( $row );
		}

		return rest_ensure_response( $rows );
	}

	public function get_sale( WP_REST_Request $request ) {
		global $wpdb;
		$table      = $this->get_table( 'sales' );
		$cust_table = $this->get_table( 'customers' );
		$inst_table = $this->get_table( 'installments' );
		$id         = absint( $request['id'] );
		$row        = $wpdb->get_row(
			$wpdb->prepare(
				"SELECT s.*, c.name AS customer_name
				 FROM {$table} s
				 LEFT JOIN {$cust_table} c ON c.id = s.customer_id
				 WHERE s.id = %d",
				$id
			),
			ARRAY_A
		);
		if ( ! $row ) {
			return new WP_Error( 'not_found', 'Satış bulunamadı.', array( 'status' => 404 ) );
		}

		$row['installments'] = $wpdb->get_results(
			$wpdb->prepare( "SELECT * FROM {$inst_table} WHERE sale_id = %d ORDER BY due_date ASC, id ASC", $id ),
			ARRAY_A
		);
		if ( $row['installments'] ) {
			foreach ( $row['installments'] as &$inst ) {
				$inst['paid'] = (int) $inst['paid'];
			}
			unset( $inst );
		}

		return rest_ensure_response( $row );
	}

	public function create_sale( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'sales' );

		$customer_id = absint( $request->get_param( 'customer_id' ) );
		if ( ! $customer_id ) {
			return new WP_Error( 'missing_customer', 'Müşteri numarası zorunludur.', array( 'status' => 400 ) );
		}

		$data = array(
			'customer_id' => $customer_id,
			'date'        => $request->get_param( 'date' ) ? sanitize_text_field( $request->get_param( 'date' ) ) : current_time( 'Y-m-d' ),
			'total'       => $request->get_param( 'total' ),
			'description' => sanitize_textarea_field( $request->get_param( 'description' ) ),
		);

		$wpdb->insert(
			$table,
			$data,
			array( '%d', '%s', '%f', '%s' )
		);

		return rest_ensure_response( array( 'id' => $wpdb->insert_id ) );
	}

	public function update_sale( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'sales' );
		$id    = absint( $request['id'] );

		$existing = $wpdb->get_var( $wpdb->prepare( "SELECT id FROM {$table} WHERE id = %d", $id ) );
		if ( ! $existing ) {
			return new WP_Error( 'not_found', 'Satış bulunamadı.', array( 'status' => 404 ) );
		}

		$data = array(
			'date'        => $request->get_param( 'date' ) ? sanitize_text_field( $request->get_param( 'date' ) ) : current_time( 'Y-m-d' ),
			'total'       => $request->get_param( 'total' ),
			'description' => sanitize_textarea_field( $request->get_param( 'description' ) ),
		);

		$wpdb->update(
			$table,
			$data,
			array( 'id' => $id ),
			array( '%s', '%f', '%s' ),
			array( '%d' )
		);

		return rest_ensure_response( array( 'updated' => true ) );
	}

	public function delete_sale( WP_REST_Request $request ) {
		global $wpdb;
		$table   = $this->get_table( 'sales' );
		$inst    = $this->get_table( 'installments' );
		$id      = absint( $request['id'] );

		$wpdb->delete( $inst, array( 'sale_id' => $id ), array( '%d' ) );
		$wpdb->delete( $table, array( 'id' => $id ), array( '%d' ) );

		return rest_ensure_response( array( 'deleted' => true ) );
	}

	// ---------------------------------------------------------------------
	// Installments (taksit)
	// ---------------------------------------------------------------------
	public function get_installments( WP_REST_Request $request ) {
		global $wpdb;
		$table   = $this->get_table( 'installments' );
		$sale_id = absint( $request->get_param( 'sale_id' ) );

		if ( $sale_id ) {
			$sql = $wpdb->prepare( "SELECT * FROM {$table} WHERE sale_id = %d ORDER BY due_date ASC, id ASC", $sale_id );
		} else {
			$sql = "SELECT * FROM {$table} ORDER BY due_date ASC, id ASC";
		}

		$rows = $wpdb->get_results( $sql, ARRAY_A );
		if ( $rows ) {
			foreach ( $rows as &$row ) {
				$row['paid'] = (int) $row['paid'];
			}
			unset( $row );
		}
		return rest_ensure_response( $rows );
	}

	public function create_installment( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'installments' );
		$has_paid_date = $this->ensure_installments_paid_date_column();

		$sale_id = absint( $request->get_param( 'sale_id' ) );
		if ( ! $sale_id ) {
			return new WP_Error( 'missing_sale', 'Satış numarası zorunludur.', array( 'status' => 400 ) );
		}

		$paid = (int) $request->get_param( 'paid' );
		$data = array(
			'sale_id'  => $sale_id,
			'due_date' => $request->get_param( 'due_date' ) ? sanitize_text_field( $request->get_param( 'due_date' ) ) : null,
			'amount'   => $request->get_param( 'amount' ),
			'paid'     => $paid,
		);
		$formats = array( '%d', '%s', '%f', '%d' );
		if ( $paid && $has_paid_date ) {
			$data['paid_date'] = current_time( 'Y-m-d' );
			$formats[]         = '%s';
		}

		$wpdb->insert( $table, $data, $formats );

		return rest_ensure_response( array( 'id' => $wpdb->insert_id ) );
	}

	public function update_installment( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'installments' );
		$id    = absint( $request['id'] );
		$has_paid_date = $this->ensure_installments_paid_date_column();

		$select_fields = $has_paid_date ? 'id, paid, paid_date' : 'id, paid';
		$existing = $wpdb->get_row(
			$wpdb->prepare( "SELECT {$select_fields} FROM {$table} WHERE id = %d", $id ),
			ARRAY_A
		);
		if ( ! $existing ) {
			return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
		}

		$data    = array();
		$formats = array();

		if ( $request->has_param( 'due_date' ) ) {
			$due              = $request->get_param( 'due_date' );
			$data['due_date'] = $due ? sanitize_text_field( $due ) : null;
			$formats[]        = '%s';
		}
		if ( $request->has_param( 'amount' ) ) {
			$data['amount'] = $request->get_param( 'amount' );
			$formats[]      = '%f';
		}
		if ( $request->has_param( 'paid' ) ) {
			$paid         = (int) $request->get_param( 'paid' );
			$data['paid'] = $paid;
			$formats[]    = '%d';
			if ( $has_paid_date ) {
				if ( $paid ) {
					$paid_date = $existing['paid_date'] ?? null;
					if ( empty( $paid_date ) || (int) $existing['paid'] !== 1 ) {
						$paid_date = current_time( 'Y-m-d' );
					}
					$data['paid_date'] = $paid_date;
				} else {
					$data['paid_date'] = null;
				}
				$formats[] = '%s';
			}
		}

		if ( empty( $data ) ) {
			return new WP_Error( 'no_fields', 'Güncellenecek alan bulunamadı.', array( 'status' => 400 ) );
		}

		$wpdb->update(
			$table,
			$data,
			array( 'id' => $id ),
			$formats,
			array( '%d' )
		);

		return rest_ensure_response( array( 'updated' => true ) );
	}

	// ---------------------------------------------------------------------
	// Locks (simple read/write coordination between devices)
	// ---------------------------------------------------------------------
	private function purge_expired_locks() {
		global $wpdb;
		$table = $this->get_table( 'locks' );
		$now   = current_time( 'mysql', true );
		$wpdb->query( $wpdb->prepare( "DELETE FROM {$table} WHERE expires_at < %s", $now ) );
	}

	private function require_device_id( WP_REST_Request $request ) {
		$device = $request->get_header( 'x-device-id' );
		if ( ! $device ) {
			return new WP_Error( 'missing_device', 'Kilit mekanizması için X-Device-Id başlığı zorunludur.', array( 'status' => 400 ) );
		}
		return sanitize_text_field( $device );
	}

	public function acquire_lock( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'locks' );

		$device = $this->require_device_id( $request );
		if ( is_wp_error( $device ) ) {
			return $device;
		}

		$record_type = sanitize_key( $request->get_param( 'record_type' ) );
		$record_id   = absint( $request->get_param( 'record_id' ) );
		$mode        = 'write' === $request->get_param( 'mode' ) ? 'write' : 'read';

		if ( ! $record_type || ! $record_id ) {
			return new WP_Error( 'invalid_lock', 'record_type ve record_id zorunludur.', array( 'status' => 400 ) );
		}

		$this->purge_expired_locks();

		if ( 'write' === $mode ) {
			$conflict = $wpdb->get_var(
				$wpdb->prepare(
					"SELECT COUNT(*) FROM {$table}
					 WHERE record_type = %s AND record_id = %d AND mode = 'write' AND device_id <> %s AND expires_at >= %s",
					$record_type,
					$record_id,
					$device,
					current_time( 'mysql', true )
				)
			);
			if ( $conflict ) {
				return new WP_Error( 'lock_conflict', 'Kayıt başka bir cihaz tarafından yazma için kilitlenmiş.', array( 'status' => 409 ) );
			}
		}

		$expires_at  = gmdate( 'Y-m-d H:i:s', time() + self::LOCK_TTL_SEC );
		$data        = array(
			'record_type' => $record_type,
			'record_id'   => $record_id,
			'device_id'   => $device,
			'mode'        => $mode,
			'expires_at'  => $expires_at,
			'updated_at'  => current_time( 'mysql', true ),
		);

		$wpdb->replace(
			$table,
			$data,
			array( '%s', '%d', '%s', '%s', '%s', '%s' )
		);

		return rest_ensure_response(
			array(
				'locked'     => true,
				'mode'       => $mode,
				'expires_at' => $data['expires_at'],
			)
		);
	}

	public function release_lock( WP_REST_Request $request ) {
		global $wpdb;
		$table = $this->get_table( 'locks' );

		$device = $this->require_device_id( $request );
		if ( is_wp_error( $device ) ) {
			return $device;
		}

		$record_type = sanitize_key( $request->get_param( 'record_type' ) );
		$record_id   = absint( $request->get_param( 'record_id' ) );

		if ( ! $record_type || ! $record_id ) {
			return new WP_Error( 'invalid_lock', 'record_type ve record_id zorunludur.', array( 'status' => 400 ) );
		}

		$wpdb->delete(
			$table,
			array(
				'record_type' => $record_type,
				'record_id'   => $record_id,
				'device_id'   => $device,
			),
			array( '%s', '%d', '%s' )
		);

		return rest_ensure_response( array( 'released' => true ) );
	}
}

Pusula_Lite_API::init();
register_activation_hook( __FILE__, array( 'Pusula_Lite_API', 'activate' ) );
