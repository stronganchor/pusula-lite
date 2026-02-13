<?php
/**
 * Plugin Name: Pusula Lite API
 * Description: REST API for the Pusula Lite desktop app (customers, sales, installments) with API key + simple record locking.
 * Version: 1.2.0
 * Update URI: https://github.com/stronganchor/pusula-lite
 * Author: Pusula Lite
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

function pusula_lite_api_get_update_branch() {
	$branch = 'main';

	if ( defined( 'PUSULA_LITE_API_UPDATE_BRANCH' ) && is_string( PUSULA_LITE_API_UPDATE_BRANCH ) ) {
		$override = trim( PUSULA_LITE_API_UPDATE_BRANCH );
		if ( '' !== $override ) {
			$branch = $override;
		}
	}

	return (string) apply_filters( 'pusula_lite_api_update_branch', $branch );
}

function pusula_lite_api_bootstrap_update_checker() {
	$checker_file = plugin_dir_path( __FILE__ ) . 'plugin-update-checker/plugin-update-checker.php';
	if ( ! file_exists( $checker_file ) ) {
		return;
	}

	require_once $checker_file;

	if ( ! class_exists( '\YahnisElsts\PluginUpdateChecker\v5\PucFactory' ) ) {
		return;
	}

	$repo_url = (string) apply_filters( 'pusula_lite_api_update_repository', 'https://github.com/stronganchor/pusula-lite' );
	$slug     = dirname( plugin_basename( __FILE__ ) );

	$update_checker = \YahnisElsts\PluginUpdateChecker\v5\PucFactory::buildUpdateChecker(
		$repo_url,
		__FILE__,
		$slug
	);

	$update_checker->setBranch( pusula_lite_api_get_update_branch() );

	if ( defined( 'PUSULA_LITE_API_GITHUB_TOKEN' ) && is_string( PUSULA_LITE_API_GITHUB_TOKEN ) ) {
		$token = trim( PUSULA_LITE_API_GITHUB_TOKEN );
		if ( '' !== $token ) {
			$update_checker->setAuthentication( $token );
		}
	}
}

pusula_lite_api_bootstrap_update_checker();

class Pusula_Lite_API {
	const VERSION                      = '1.2.0';
	const LEGACY_PROFILE_MIGRATION_VER = '1.1.0';
	const OPTION_KEY                   = 'pusula_lite_api_key';
	const OPTION_BUSINESS_PROFILE      = 'pusula_lite_business_profile';
	const OPTION_PLUGIN_VERSION        = 'pusula_lite_api_version';
	const OPTION_LEGACY_PROFILE_DONE   = 'pusula_lite_legacy_profile_migrated';
	const LOCK_TTL_SEC                 = 120; // seconds
	const ROLE                         = 'pusula_user';

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
		add_action( 'init', array( $this, 'maybe_run_upgrade_tasks' ), 1 );
		add_action( 'rest_api_init', array( $this, 'register_routes' ) );
		add_action( 'admin_menu', array( $this, 'register_admin_page' ) );
		add_shortcode( 'pusula_lite_app', array( $this, 'render_shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'register_assets' ) );
	}

	// ---------------------------------------------------------------------
	// Activation
	// ---------------------------------------------------------------------
	public static function activate() {
		$stored_version   = (string) get_option( self::OPTION_PLUGIN_VERSION, '' );
		$has_existing_key = ! empty( get_option( self::OPTION_KEY ) );

		self::create_tables();
		self::migrate_legacy_paid_installments_to_payments();
		self::maybe_generate_key();
		self::register_role();

		if ( ( '' === $stored_version && $has_existing_key ) || ( '' !== $stored_version && version_compare( $stored_version, self::LEGACY_PROFILE_MIGRATION_VER, '<' ) ) ) {
			self::migrate_legacy_business_profile_once();
		}

		update_option( self::OPTION_PLUGIN_VERSION, self::VERSION );
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

		$installment_payments = "CREATE TABLE {$prefix}installment_payments (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			installment_id BIGINT UNSIGNED NOT NULL,
			amount DECIMAL(10,2) NOT NULL,
			payment_date DATE NOT NULL,
			created_at DATETIME NOT NULL,
			PRIMARY KEY (id),
			KEY installment_idx (installment_id),
			KEY payment_date_idx (payment_date)
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
		dbDelta( $installment_payments );
		dbDelta( $contacts );
		dbDelta( $locks );
	}

	private static function migrate_legacy_paid_installments_to_payments() {
		global $wpdb;
		$prefix        = $wpdb->prefix . 'pusula_';
		$inst_table    = $prefix . 'installments';
		$payment_table = $prefix . 'installment_payments';

		$rows = $wpdb->get_results(
			"SELECT i.id, i.amount, i.paid_date, i.due_date
			 FROM {$inst_table} i
			 LEFT JOIN {$payment_table} p ON p.installment_id = i.id
			 WHERE COALESCE(i.paid, 0) = 1
			 GROUP BY i.id, i.amount, i.paid_date, i.due_date
			 HAVING COUNT(p.id) = 0",
			ARRAY_A
		);

		if ( empty( $rows ) ) {
			return;
		}

		foreach ( $rows as $row ) {
			$amount = round( (float) $row['amount'], 2 );
			if ( $amount <= 0 ) {
				continue;
			}
			$paid_date = ! empty( $row['paid_date'] ) ? (string) $row['paid_date'] : '';
			if ( ! preg_match( '/^\d{4}-\d{2}-\d{2}$/', $paid_date ) ) {
				$due_date  = ! empty( $row['due_date'] ) ? (string) $row['due_date'] : '';
				$paid_date = preg_match( '/^\d{4}-\d{2}-\d{2}$/', $due_date ) ? $due_date : current_time( 'Y-m-d' );
			}

			$wpdb->insert(
				$payment_table,
				array(
					'installment_id' => (int) $row['id'],
					'amount'         => $amount,
					'payment_date'   => $paid_date,
					'created_at'     => current_time( 'mysql' ),
				),
				array( '%d', '%f', '%s', '%s' )
			);
		}
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

	public function maybe_run_upgrade_tasks() {
		$stored_version = (string) get_option( self::OPTION_PLUGIN_VERSION, '' );

		if ( '' === $stored_version ) {
			if ( self::is_existing_install() ) {
				self::create_tables();
				self::migrate_legacy_paid_installments_to_payments();
				self::migrate_legacy_business_profile_once();
			}
			update_option( self::OPTION_PLUGIN_VERSION, self::VERSION );
			return;
		}

		if ( version_compare( $stored_version, self::LEGACY_PROFILE_MIGRATION_VER, '<' ) ) {
			self::migrate_legacy_business_profile_once();
		}

		if ( version_compare( $stored_version, self::VERSION, '<' ) ) {
			self::create_tables();
			self::migrate_legacy_paid_installments_to_payments();
			update_option( self::OPTION_PLUGIN_VERSION, self::VERSION );
		}
	}

	private static function is_existing_install() {
		return ! empty( get_option( self::OPTION_KEY ) );
	}

	private static function get_default_business_profile() {
		return array(
			'name'       => '',
			'address'    => '',
			'phone'      => '',
			'website'    => '',
			'footer_sub' => '',
		);
	}

	private static function get_legacy_business_profile() {
		return array(
			'name'       => 'ENES BEKO',
			'address'    => 'KOZAN CD. PTT EVLERİ KAVŞAĞI NO: 689, ADANA',
			'phone'      => '(0322) 329 92 32',
			'website'    => 'https://enesbeko.com',
			'footer_sub' => 'ENES EFY KARDEŞLER',
		);
	}

	private static function sanitize_business_profile( $raw_profile ) {
		$profile = is_array( $raw_profile ) ? $raw_profile : array();

		return array(
			'name'       => sanitize_text_field( isset( $profile['name'] ) ? $profile['name'] : '' ),
			'address'    => sanitize_textarea_field( isset( $profile['address'] ) ? $profile['address'] : '' ),
			'phone'      => sanitize_text_field( isset( $profile['phone'] ) ? $profile['phone'] : '' ),
			'website'    => esc_url_raw( trim( (string) ( isset( $profile['website'] ) ? $profile['website'] : '' ) ) ),
			'footer_sub' => sanitize_text_field( isset( $profile['footer_sub'] ) ? $profile['footer_sub'] : '' ),
		);
	}

	private static function get_business_profile() {
		$defaults = self::get_default_business_profile();
		$stored   = get_option( self::OPTION_BUSINESS_PROFILE, array() );
		$stored   = is_array( $stored ) ? $stored : array();
		$merged   = wp_parse_args( $stored, $defaults );
		return self::sanitize_business_profile( $merged );
	}

	private static function has_business_profile_values( $profile ) {
		foreach ( self::get_default_business_profile() as $key => $default ) {
			if ( '' !== trim( (string) ( isset( $profile[ $key ] ) ? $profile[ $key ] : $default ) ) ) {
				return true;
			}
		}
		return false;
	}

	private static function migrate_legacy_business_profile_once() {
		if ( get_option( self::OPTION_LEGACY_PROFILE_DONE ) ) {
			return;
		}

		$current_profile = self::get_business_profile();
		if ( ! self::has_business_profile_values( $current_profile ) ) {
			update_option( self::OPTION_BUSINESS_PROFILE, self::get_legacy_business_profile() );
		}

		update_option( self::OPTION_LEGACY_PROFILE_DONE, 1 );
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
	}

	public function render_settings_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}

		if ( isset( $_POST['pusula_regen_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['pusula_regen_nonce'] ) ), 'pusula_regen_key' ) ) {
			update_option( self::OPTION_KEY, self::generate_api_key() );
			echo '<div class="notice notice-success is-dismissible"><p>API key regenerated.</p></div>';
		}

		if ( isset( $_POST['pusula_business_nonce'] ) ) {
			$nonce_ok = wp_verify_nonce(
				sanitize_text_field( wp_unslash( $_POST['pusula_business_nonce'] ) ),
				'pusula_save_business'
			);

			if ( $nonce_ok ) {
				$business_profile = self::sanitize_business_profile(
					array(
						'name'       => isset( $_POST['pusula_business_name'] ) ? wp_unslash( $_POST['pusula_business_name'] ) : '',
						'address'    => isset( $_POST['pusula_business_address'] ) ? wp_unslash( $_POST['pusula_business_address'] ) : '',
						'phone'      => isset( $_POST['pusula_business_phone'] ) ? wp_unslash( $_POST['pusula_business_phone'] ) : '',
						'website'    => isset( $_POST['pusula_business_website'] ) ? wp_unslash( $_POST['pusula_business_website'] ) : '',
						'footer_sub' => isset( $_POST['pusula_business_footer_sub'] ) ? wp_unslash( $_POST['pusula_business_footer_sub'] ) : '',
					)
				);
				update_option( self::OPTION_BUSINESS_PROFILE, $business_profile );
				echo '<div class="notice notice-success is-dismissible"><p>Business information saved.</p></div>';
			} else {
				echo '<div class="notice notice-error is-dismissible"><p>Business information could not be saved due to a security check failure.</p></div>';
			}
		}

		$key             = get_option( self::OPTION_KEY );
		$business_profile = self::get_business_profile();
		?>
		<div class="wrap">
			<h1>Pusula Lite API</h1>
			<h2>API Key</h2>
			<p>Provide the API key below to the desktop client. Keep it secret.</p>
			<p><strong>API Key:</strong></p>
			<code style="font-size:14px;"><?php echo esc_html( $key ); ?></code>
			<form method="post" style="margin-top:16px;">
				<?php wp_nonce_field( 'pusula_regen_key', 'pusula_regen_nonce' ); ?>
				<button type="submit" class="button button-secondary">Regenerate Key</button>
			</form>

			<hr style="margin:24px 0;">

			<h2>Business Information</h2>
			<p>This information is used on printed receipts (makbuz).</p>
			<form method="post">
				<?php wp_nonce_field( 'pusula_save_business', 'pusula_business_nonce' ); ?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><label for="pusula-business-name">Business Name</label></th>
						<td><input type="text" class="regular-text" id="pusula-business-name" name="pusula_business_name" value="<?php echo esc_attr( $business_profile['name'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="pusula-business-address">Address</label></th>
						<td><textarea class="large-text" rows="3" id="pusula-business-address" name="pusula_business_address"><?php echo esc_textarea( $business_profile['address'] ); ?></textarea></td>
					</tr>
					<tr>
						<th scope="row"><label for="pusula-business-phone">Phone</label></th>
						<td><input type="text" class="regular-text" id="pusula-business-phone" name="pusula_business_phone" value="<?php echo esc_attr( $business_profile['phone'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="pusula-business-website">Website</label></th>
						<td><input type="url" class="regular-text" id="pusula-business-website" name="pusula_business_website" value="<?php echo esc_attr( $business_profile['website'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="pusula-business-footer-sub">Footer Line</label></th>
						<td><input type="text" class="regular-text" id="pusula-business-footer-sub" name="pusula_business_footer_sub" value="<?php echo esc_attr( $business_profile['footer_sub'] ); ?>"></td>
					</tr>
				</table>
				<?php submit_button( 'Save Business Information' ); ?>
			</form>
		</div>
		<?php
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

		$business_profile = self::get_business_profile();
		wp_localize_script(
			'pusula-lite-app',
			'PusulaApp',
			array(
				'apiBase'  => esc_url_raw( rest_url( 'pusula/v1' ) ),
				'nonce'    => wp_create_nonce( 'wp_rest' ),
				'business' => array(
					'name'      => $business_profile['name'],
					'address'   => $business_profile['address'],
					'phone'     => $business_profile['phone'],
					'website'   => $business_profile['website'],
					'footerSub' => $business_profile['footer_sub'],
				),
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

		register_rest_route(
			$namespace,
			'/installments/(?P<id>\d+)/payments',
			array(
				'methods'             => WP_REST_Server::READABLE,
				'callback'            => array( $this, 'get_installment_payments' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/installments/(?P<id>\d+)/payments',
			array(
				'methods'             => WP_REST_Server::CREATABLE,
				'callback'            => array( $this, 'create_installment_payment' ),
				'permission_callback' => array( $this, 'permission_callback' ),
			)
		);

		register_rest_route(
			$namespace,
			'/installments/(?P<id>\d+)/payments/(?P<payment_id>\d+)',
			array(
				'methods'             => WP_REST_Server::DELETABLE,
				'callback'            => array( $this, 'delete_installment_payment' ),
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

	private function to_money_float( $value ) {
		return round( (float) $value, 2 );
	}

	private function to_money_cents( $value ) {
		return (int) round( $this->to_money_float( $value ) * 100 );
	}

	private function is_valid_iso_date( $value ) {
		return is_string( $value ) && (bool) preg_match( '/^\d{4}-\d{2}-\d{2}$/', $value );
	}

	private function get_installment_payment_summary( array $installment_ids, $include_payments = false ) {
		global $wpdb;
		$payment_table = $this->get_table( 'installment_payments' );
		$ids           = array_values( array_filter( array_map( 'intval', $installment_ids ) ) );

		if ( empty( $ids ) ) {
			return array();
		}

		$placeholders = implode( ',', array_fill( 0, count( $ids ), '%d' ) );
		$rows         = $wpdb->get_results(
			$wpdb->prepare(
				"SELECT id, installment_id, amount, payment_date, created_at
				 FROM {$payment_table}
				 WHERE installment_id IN ({$placeholders})
				 ORDER BY payment_date ASC, id ASC",
				$ids
			),
			ARRAY_A
		);

		$summary = array();
		foreach ( $ids as $id ) {
			$summary[ $id ] = array(
				'paid_amount'         => 0.0,
				'payment_count'       => 0,
				'last_payment_id'     => null,
				'last_payment_amount' => 0.0,
				'last_payment_date'   => null,
				'payments'            => array(),
			);
		}

		foreach ( $rows as $row ) {
			$installment_id = (int) $row['installment_id'];
			if ( ! isset( $summary[ $installment_id ] ) ) {
				$summary[ $installment_id ] = array(
					'paid_amount'         => 0.0,
					'payment_count'       => 0,
					'last_payment_id'     => null,
					'last_payment_amount' => 0.0,
					'last_payment_date'   => null,
					'payments'            => array(),
				);
			}
			$amount = $this->to_money_float( $row['amount'] );
			$summary[ $installment_id ]['paid_amount']   = $this->to_money_float( $summary[ $installment_id ]['paid_amount'] + $amount );
			$summary[ $installment_id ]['payment_count'] = (int) $summary[ $installment_id ]['payment_count'] + 1;
			$summary[ $installment_id ]['last_payment_id']     = (int) $row['id'];
			$summary[ $installment_id ]['last_payment_amount'] = $amount;
			$summary[ $installment_id ]['last_payment_date']   = $row['payment_date'];

			if ( $include_payments ) {
				$summary[ $installment_id ]['payments'][] = array(
					'id'           => (int) $row['id'],
					'installment_id'=> $installment_id,
					'amount'       => $amount,
					'payment_date' => $row['payment_date'],
					'created_at'   => $row['created_at'],
				);
			}
		}

		return $summary;
	}

	private function enrich_installments_with_payment_data( array $rows, $id_key = 'id', $include_payments = false ) {
		$ids = array();
		foreach ( $rows as $row ) {
			$rid = isset( $row[ $id_key ] ) ? (int) $row[ $id_key ] : 0;
			if ( $rid > 0 ) {
				$ids[] = $rid;
			}
		}
		$summary = $this->get_installment_payment_summary( $ids, $include_payments );

		foreach ( $rows as &$row ) {
			$rid    = isset( $row[ $id_key ] ) ? (int) $row[ $id_key ] : 0;
			$amount = $this->to_money_float( isset( $row['amount'] ) ? $row['amount'] : 0 );
			$info   = isset( $summary[ $rid ] ) ? $summary[ $rid ] : array(
				'paid_amount'         => 0.0,
				'payment_count'       => 0,
				'last_payment_id'     => null,
				'last_payment_amount' => 0.0,
				'last_payment_date'   => null,
				'payments'            => array(),
			);

			$paid_amount = $this->to_money_float( $info['paid_amount'] );
			$remaining   = $this->to_money_float( max( 0, $amount - $paid_amount ) );
			$is_paid     = $remaining <= 0.00001 ? 1 : 0;

			// Backward compatibility: legacy rows may have paid=1 without payment records.
			if ( (int) $info['payment_count'] === 0 && isset( $row['paid'] ) && (int) $row['paid'] === 1 ) {
				$paid_amount = $amount;
				$remaining   = 0.0;
				$is_paid     = 1;
			}

			$row['amount']             = $amount;
			$row['paid_amount']        = $paid_amount;
			$row['remaining_amount']   = $remaining;
			$row['payment_count']      = (int) $info['payment_count'];
			$row['last_payment_id']    = $info['last_payment_id'] ? (int) $info['last_payment_id'] : null;
			$row['last_payment_amount']= $this->to_money_float( $info['last_payment_amount'] );
			$row['last_payment_date']  = $info['last_payment_date'];
			$row['paid']               = $is_paid;

			if ( $is_paid && empty( $row['paid_date'] ) && ! empty( $info['last_payment_date'] ) ) {
				$row['paid_date'] = $info['last_payment_date'];
			}

			if ( $include_payments ) {
				$running = 0.0;
				$payments = array();
				foreach ( $info['payments'] as $payment ) {
					$running = $this->to_money_float( $running + $this->to_money_float( $payment['amount'] ) );
					$payment['running_paid_amount']      = $running;
					$payment['remaining_after_payment']  = $this->to_money_float( max( 0, $amount - $running ) );
					$payments[] = $payment;
				}
				$row['payments'] = $payments;
			}
		}
		unset( $row );

		return $rows;
	}

	private function recalculate_installment_payment_status( $installment_id ) {
		global $wpdb;
		$table         = $this->get_table( 'installments' );
		$installment_id = absint( $installment_id );
		if ( ! $installment_id ) {
			return null;
		}

		$existing = $wpdb->get_row(
			$wpdb->prepare( "SELECT id, amount FROM {$table} WHERE id = %d", $installment_id ),
			ARRAY_A
		);
		if ( ! $existing ) {
			return null;
		}

		$amount  = $this->to_money_float( $existing['amount'] );
		$summary = $this->get_installment_payment_summary( array( $installment_id ), false );
		$info    = isset( $summary[ $installment_id ] ) ? $summary[ $installment_id ] : array(
			'paid_amount'       => 0.0,
			'payment_count'     => 0,
			'last_payment_date' => null,
		);
		$paid_amount = $this->to_money_float( $info['paid_amount'] );
		$remaining   = $this->to_money_float( max( 0, $amount - $paid_amount ) );
		$is_paid     = $remaining <= 0.00001 ? 1 : 0;

		$has_paid_date = $this->ensure_installments_paid_date_column();
		$data          = array( 'paid' => $is_paid );
		$formats       = array( '%d' );
		if ( $has_paid_date ) {
			$data['paid_date'] = $is_paid ? $info['last_payment_date'] : null;
			$formats[]         = '%s';
		}

		$wpdb->update(
			$table,
			$data,
			array( 'id' => $installment_id ),
			$formats,
			array( '%d' )
		);

		return array(
			'amount'           => $amount,
			'paid_amount'      => $paid_amount,
			'remaining_amount' => $remaining,
			'paid'             => $is_paid,
			'paid_date'        => $is_paid ? $info['last_payment_date'] : null,
			'payment_count'    => (int) $info['payment_count'],
		);
	}

	private function get_installment_row_with_payments( $installment_id, $include_payments = false ) {
		global $wpdb;
		$table = $this->get_table( 'installments' );
		$row   = $wpdb->get_row(
			$wpdb->prepare( "SELECT * FROM {$table} WHERE id = %d", absint( $installment_id ) ),
			ARRAY_A
		);
		if ( ! $row ) {
			return null;
		}
		$rows = $this->enrich_installments_with_payment_data( array( $row ), 'id', $include_payments );
		return isset( $rows[0] ) ? $rows[0] : null;
	}

	private function create_installment_payment_internal( $installment_id, $amount, $payment_date = null ) {
		global $wpdb;
		$installment = $this->get_installment_row_with_payments( $installment_id, false );
		if ( ! $installment ) {
			return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
		}

		$remaining_cents = $this->to_money_cents( $installment['remaining_amount'] );
		if ( $remaining_cents <= 0 ) {
			return new WP_Error( 'already_paid', 'Bu taksit tamamen ödenmiş.', array( 'status' => 400 ) );
		}

		$pay_cents = $this->to_money_cents( $amount );
		if ( $pay_cents <= 0 ) {
			return new WP_Error( 'invalid_amount', 'Ödeme tutarı 0 dan büyük olmalıdır.', array( 'status' => 400 ) );
		}
		if ( $pay_cents > $remaining_cents ) {
			return new WP_Error( 'amount_exceeds_remaining', 'Ödeme tutarı kalan borçtan büyük olamaz.', array( 'status' => 400 ) );
		}

		$pay_date = $payment_date ? sanitize_text_field( $payment_date ) : current_time( 'Y-m-d' );
		if ( ! $this->is_valid_iso_date( $pay_date ) ) {
			return new WP_Error( 'invalid_date', 'Ödeme tarihi geçersiz.', array( 'status' => 400 ) );
		}

		$payment_table = $this->get_table( 'installment_payments' );
		$pay_amount    = $this->to_money_float( $pay_cents / 100 );

		$inserted = $wpdb->insert(
			$payment_table,
			array(
				'installment_id' => (int) $installment_id,
				'amount'         => $pay_amount,
				'payment_date'   => $pay_date,
				'created_at'     => current_time( 'mysql' ),
			),
			array( '%d', '%f', '%s', '%s' )
		);

		if ( false === $inserted ) {
			return new WP_Error( 'payment_insert_failed', 'Ödeme kaydı oluşturulamadı.', array( 'status' => 500 ) );
		}

		$payment_id  = (int) $wpdb->insert_id;
		$before_paid = $this->to_money_float( $installment['paid_amount'] );
		$status      = $this->recalculate_installment_payment_status( $installment_id );
		$updated     = $this->get_installment_row_with_payments( $installment_id, false );

		return array(
			'payment' => array(
				'id'                       => $payment_id,
				'installment_id'           => (int) $installment_id,
				'amount'                   => $pay_amount,
				'payment_date'             => $pay_date,
				'paid_before'              => $before_paid,
				'paid_after'               => $status ? $this->to_money_float( $status['paid_amount'] ) : $this->to_money_float( $before_paid + $pay_amount ),
				'remaining_after_payment'  => $status ? $this->to_money_float( $status['remaining_amount'] ) : $this->to_money_float( max( 0, (float) $installment['remaining_amount'] - $pay_amount ) ),
			),
			'installment' => $updated ? $updated : $installment,
		);
	}

	private function enrich_customers_with_debt_totals( array $rows ) {
		global $wpdb;
		$sales_table    = $this->get_table( 'sales' );
		$inst_table     = $this->get_table( 'installments' );
		$payments_table = $this->get_table( 'installment_payments' );
		$customer_ids   = array_values( array_filter( array_map( 'intval', wp_list_pluck( $rows, 'id' ) ) ) );

		if ( empty( $customer_ids ) ) {
			return $rows;
		}

		$placeholders = implode( ',', array_fill( 0, count( $customer_ids ), '%d' ) );
		$debt_rows = $wpdb->get_results(
			$wpdb->prepare(
				"SELECT
					s.customer_id,
					COALESCE(
						SUM(
							CASE
								WHEN COALESCE(i.amount, 0) - COALESCE(p.paid_total, 0) > 0
									THEN COALESCE(i.amount, 0) - COALESCE(p.paid_total, 0)
								ELSE 0
							END
						),
						0
					) AS debt_total
				FROM {$sales_table} s
				INNER JOIN {$inst_table} i ON i.sale_id = s.id
				LEFT JOIN (
					SELECT installment_id, SUM(amount) AS paid_total
					FROM {$payments_table}
					GROUP BY installment_id
				) p ON p.installment_id = i.id
				WHERE s.customer_id IN ({$placeholders})
				GROUP BY s.customer_id",
				$customer_ids
			),
			ARRAY_A
		);

		$lookup = array();
		foreach ( $debt_rows as $debt_row ) {
			$lookup[ (int) $debt_row['customer_id'] ] = $this->to_money_float( $debt_row['debt_total'] );
		}

		foreach ( $rows as &$row ) {
			$row['debt_total'] = isset( $lookup[ (int) $row['id'] ] ) ? $lookup[ (int) $row['id'] ] : 0.0;
		}
		unset( $row );

		return $rows;
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
				$pay_table   = $this->get_table( 'installment_payments' );
				$today       = current_time( 'Y-m-d' );
				$placeholders = implode( ',', array_fill( 0, count( $ids ), '%d' ) );
				$params = array_merge( $ids, array( $today ) );
				$late_ids = $wpdb->get_col(
					$wpdb->prepare(
						"SELECT DISTINCT s.customer_id
						 FROM {$sales_table} s
						 INNER JOIN {$inst_table} i ON i.sale_id = s.id
						 LEFT JOIN (
						 	SELECT installment_id, SUM(amount) AS paid_total
						 	FROM {$pay_table}
						 	GROUP BY installment_id
						 ) p ON p.installment_id = i.id
						 WHERE s.customer_id IN ({$placeholders})
						   AND COALESCE(i.amount, 0) - COALESCE(p.paid_total, 0) > 0
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

		if ( $rows ) {
			$rows = $this->enrich_customers_with_debt_totals( $rows );
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
		$with_debt       = $this->enrich_customers_with_debt_totals( array( $row ) );
		$row['debt_total'] = isset( $with_debt[0]['debt_total'] ) ? $with_debt[0]['debt_total'] : 0.0;

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
		$pay_table   = $this->get_table( 'installment_payments' );
		$contact_tbl = $this->get_table( 'contacts' );

		// delete installments for this customer's sales
		$sale_ids = $wpdb->get_col( $wpdb->prepare( "SELECT id FROM {$sales_table} WHERE customer_id = %d", $id ) );
		if ( $sale_ids ) {
			foreach ( $sale_ids as $sid ) {
				$installment_ids = $wpdb->get_col( $wpdb->prepare( "SELECT id FROM {$inst_table} WHERE sale_id = %d", $sid ) );
				if ( $installment_ids ) {
					foreach ( $installment_ids as $installment_id ) {
						$wpdb->delete( $pay_table, array( 'installment_id' => $installment_id ), array( '%d' ) );
					}
				}
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
			$inst_rows = $this->enrich_installments_with_payment_data( $inst_rows, 'id', true );
			$grouped = array();
			foreach ( $inst_rows as $inst ) {
				$sid = (int) $inst['sale_id'];
				if ( ! isset( $grouped[ $sid ] ) ) {
					$grouped[ $sid ] = array();
				}
				$grouped[ $sid ][] = $inst;
			}
			foreach ( $rows as &$row ) {
				$installments = $grouped[ $row['id'] ] ?? array();
				$row['installments'] = $installments;
				$row['installments_total'] = $this->to_money_float(
					array_reduce(
						$installments,
						function( $sum, $inst ) {
							return $sum + (float) ( isset( $inst['amount'] ) ? $inst['amount'] : 0 );
						},
						0
					)
				);
				$row['installments_paid_total'] = $this->to_money_float(
					array_reduce(
						$installments,
						function( $sum, $inst ) {
							return $sum + (float) ( isset( $inst['paid_amount'] ) ? $inst['paid_amount'] : 0 );
						},
						0
					)
				);
				$row['installments_remaining_total'] = $this->to_money_float(
					array_reduce(
						$installments,
						function( $sum, $inst ) {
							return $sum + (float) ( isset( $inst['remaining_amount'] ) ? $inst['remaining_amount'] : 0 );
						},
						0
					)
				);
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
		$where         = array( 'i.due_date IS NOT NULL' );
		$params        = array();
		$paid_date_select = $has_paid_date ? 'i.paid_date' : 'NULL AS paid_date';

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
		$rows = $this->enrich_installments_with_payment_data( $rows, 'installment_id', false );

		$filtered = array();
		foreach ( $rows as $row ) {
			$remaining    = $this->to_money_float( isset( $row['remaining_amount'] ) ? $row['remaining_amount'] : 0 );
			$paid_date    = isset( $row['paid_date'] ) ? (string) $row['paid_date'] : '';
			$is_paid_today = $remaining <= 0.00001 && $paid_date === $today;
			if ( $remaining > 0.00001 || $is_paid_today ) {
				$row['installment_amount'] = $this->to_money_float( isset( $row['amount'] ) ? $row['amount'] : 0 );
				$filtered[] = $row;
			}
		}

		return rest_ensure_response( $filtered );
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
		$row['installments'] = $this->enrich_installments_with_payment_data( $row['installments'], 'id', true );
		$row['installments_total'] = $this->to_money_float(
			array_reduce(
				$row['installments'],
				function( $sum, $inst ) {
					return $sum + (float) ( isset( $inst['amount'] ) ? $inst['amount'] : 0 );
				},
				0
			)
		);
		$row['installments_paid_total'] = $this->to_money_float(
			array_reduce(
				$row['installments'],
				function( $sum, $inst ) {
					return $sum + (float) ( isset( $inst['paid_amount'] ) ? $inst['paid_amount'] : 0 );
				},
				0
			)
		);
		$row['installments_remaining_total'] = $this->to_money_float(
			array_reduce(
				$row['installments'],
				function( $sum, $inst ) {
					return $sum + (float) ( isset( $inst['remaining_amount'] ) ? $inst['remaining_amount'] : 0 );
				},
				0
			)
		);

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
		$pay     = $this->get_table( 'installment_payments' );
		$id      = absint( $request['id'] );

		$installment_ids = $wpdb->get_col( $wpdb->prepare( "SELECT id FROM {$inst} WHERE sale_id = %d", $id ) );
		if ( $installment_ids ) {
			foreach ( $installment_ids as $installment_id ) {
				$wpdb->delete( $pay, array( 'installment_id' => $installment_id ), array( '%d' ) );
			}
		}
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
		$rows = $this->enrich_installments_with_payment_data( $rows, 'id', true );
		return rest_ensure_response( $rows );
	}

	public function create_installment( WP_REST_Request $request ) {
		global $wpdb;
		$table         = $this->get_table( 'installments' );
		$has_paid_date = $this->ensure_installments_paid_date_column();

		$sale_id = absint( $request->get_param( 'sale_id' ) );
		if ( ! $sale_id ) {
			return new WP_Error( 'missing_sale', 'Satış numarası zorunludur.', array( 'status' => 400 ) );
		}

		$due_date = $request->get_param( 'due_date' ) ? sanitize_text_field( $request->get_param( 'due_date' ) ) : null;
		if ( $due_date && ! $this->is_valid_iso_date( $due_date ) ) {
			return new WP_Error( 'invalid_due_date', 'Vade tarihi geçersiz.', array( 'status' => 400 ) );
		}

		$amount        = $this->to_money_float( $request->get_param( 'amount' ) );
		$requested_paid = (int) $request->get_param( 'paid' ) === 1;
		$data = array(
			'sale_id'  => $sale_id,
			'due_date' => $due_date,
			'amount'   => $amount,
			'paid'     => 0,
		);
		$formats = array( '%d', '%s', '%f', '%d' );
		if ( $has_paid_date ) {
			$data['paid_date'] = null;
			$formats[]         = '%s';
		}

		$inserted = $wpdb->insert( $table, $data, $formats );
		if ( false === $inserted ) {
			return new WP_Error( 'insert_failed', 'Taksit kaydı oluşturulamadı.', array( 'status' => 500 ) );
		}
		$installment_id = (int) $wpdb->insert_id;

		if ( $requested_paid && $amount > 0 ) {
			$payment_result = $this->create_installment_payment_internal(
				$installment_id,
				$amount,
				$request->get_param( 'payment_date' ) ? sanitize_text_field( $request->get_param( 'payment_date' ) ) : null
			);
			if ( is_wp_error( $payment_result ) ) {
				return $payment_result;
			}
		} else {
			$this->recalculate_installment_payment_status( $installment_id );
		}

		return rest_ensure_response( array( 'id' => $installment_id ) );
	}

	public function update_installment( WP_REST_Request $request ) {
		global $wpdb;
		$table   = $this->get_table( 'installments' );
		$pay_tbl = $this->get_table( 'installment_payments' );
		$id      = absint( $request['id'] );
		$existing = $wpdb->get_row(
			$wpdb->prepare( 'SELECT id, amount FROM ' . $table . ' WHERE id = %d', $id ),
			ARRAY_A
		);
		if ( ! $existing ) {
			return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
		}

		$data    = array();
		$formats = array();
		$should_recalculate = false;

		if ( $request->has_param( 'due_date' ) ) {
			$due              = $request->get_param( 'due_date' );
			$data['due_date'] = $due ? sanitize_text_field( $due ) : null;
			if ( $data['due_date'] && ! $this->is_valid_iso_date( $data['due_date'] ) ) {
				return new WP_Error( 'invalid_due_date', 'Vade tarihi geçersiz.', array( 'status' => 400 ) );
			}
			$formats[]        = '%s';
		}
		if ( $request->has_param( 'amount' ) ) {
			$data['amount'] = $this->to_money_float( $request->get_param( 'amount' ) );
			$formats[]      = '%f';
			$should_recalculate = true;
		}

		if ( ! empty( $data ) ) {
			$wpdb->update(
				$table,
				$data,
				array( 'id' => $id ),
				$formats,
				array( '%d' )
			);
		}

		if ( $request->has_param( 'paid' ) ) {
			$paid = (int) $request->get_param( 'paid' );
			if ( 1 === $paid ) {
				$installment = $this->get_installment_row_with_payments( $id, false );
				if ( ! $installment ) {
					return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
				}
				$remaining = $this->to_money_float( $installment['remaining_amount'] );
				if ( $remaining > 0 ) {
					$payment_result = $this->create_installment_payment_internal(
						$id,
						$remaining,
						$request->get_param( 'payment_date' ) ? sanitize_text_field( $request->get_param( 'payment_date' ) ) : null
					);
					if ( is_wp_error( $payment_result ) ) {
						return $payment_result;
					}
				}
			} else {
				$wpdb->delete( $pay_tbl, array( 'installment_id' => $id ), array( '%d' ) );
				$this->recalculate_installment_payment_status( $id );
			}
		} elseif ( $should_recalculate ) {
			$this->recalculate_installment_payment_status( $id );
		}

		if ( empty( $data ) && ! $request->has_param( 'paid' ) ) {
			return new WP_Error( 'no_fields', 'Güncellenecek alan bulunamadı.', array( 'status' => 400 ) );
		}

		return rest_ensure_response(
			array(
				'updated'     => true,
				'installment' => $this->get_installment_row_with_payments( $id, true ),
			)
		);
	}

	public function get_installment_payments( WP_REST_Request $request ) {
		$id          = absint( $request['id'] );
		$installment = $this->get_installment_row_with_payments( $id, true );
		if ( ! $installment ) {
			return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
		}

		return rest_ensure_response(
			array(
				'installment' => $installment,
				'payments'    => isset( $installment['payments'] ) ? $installment['payments'] : array(),
			)
		);
	}

	public function create_installment_payment( WP_REST_Request $request ) {
		$id          = absint( $request['id'] );
		$installment = $this->get_installment_row_with_payments( $id, false );
		if ( ! $installment ) {
			return new WP_Error( 'not_found', 'Taksit bulunamadı.', array( 'status' => 404 ) );
		}

		$remaining = $this->to_money_float( $installment['remaining_amount'] );
		$amount    = $request->has_param( 'amount' )
			? $this->to_money_float( $request->get_param( 'amount' ) )
			: $remaining;

		$result = $this->create_installment_payment_internal(
			$id,
			$amount,
			$request->get_param( 'payment_date' ) ? sanitize_text_field( $request->get_param( 'payment_date' ) ) : null
		);
		if ( is_wp_error( $result ) ) {
			return $result;
		}

		return rest_ensure_response( $result );
	}

	public function delete_installment_payment( WP_REST_Request $request ) {
		global $wpdb;
		$id         = absint( $request['id'] );
		$payment_id = absint( $request['payment_id'] );
		$pay_table  = $this->get_table( 'installment_payments' );

		if ( ! $id || ! $payment_id ) {
			return new WP_Error( 'invalid_payment', 'Geçersiz ödeme kaydı.', array( 'status' => 400 ) );
		}

		$payment = $wpdb->get_row(
			$wpdb->prepare( "SELECT id, installment_id FROM {$pay_table} WHERE id = %d", $payment_id ),
			ARRAY_A
		);
		if ( ! $payment || (int) $payment['installment_id'] !== $id ) {
			return new WP_Error( 'not_found', 'Ödeme kaydı bulunamadı.', array( 'status' => 404 ) );
		}

		$wpdb->delete( $pay_table, array( 'id' => $payment_id ), array( '%d' ) );
		$this->recalculate_installment_payment_status( $id );

		return rest_ensure_response(
			array(
				'deleted'     => true,
				'installment' => $this->get_installment_row_with_payments( $id, true ),
			)
		);
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
