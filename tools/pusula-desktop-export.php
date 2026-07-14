<?php
/**
 * One-time Pusula Lite to Pusula Desktop export command.
 *
 * Load this file explicitly with WP-CLI. It is intentionally not included by
 * the plugin and therefore does not add routes or change normal plugin runtime.
 */

if ( ! class_exists( 'Pusula_Desktop_Legacy_Exporter' ) ) {
	class Pusula_Desktop_Legacy_Exporter {
		const FORMAT_VERSION = 1;
		const SOURCE          = 'pusula-lite-wordpress';

		/** @var wpdb */
		private $wpdb;

		/** @var callable */
		private $option_reader;

		/** @var string */
		private $source_version;

		/** @var callable */
		private $clock;

		/** @var bool */
		private $snapshot_started = false;

		/**
		 * @param wpdb     $wpdb           WordPress database connection.
		 * @param callable $option_reader  Callback compatible with get_option().
		 * @param string   $source_version Active Pusula Lite plugin version.
		 * @param callable $clock          Optional UTC RFC3339 timestamp callback.
		 */
		public function __construct( $wpdb, $option_reader, $source_version, $clock = null ) {
			if ( ! is_object( $wpdb ) || ! isset( $wpdb->prefix ) ) {
				throw new InvalidArgumentException( 'A valid WordPress database connection is required.' );
			}
			if ( ! is_callable( $option_reader ) ) {
				throw new InvalidArgumentException( 'The option reader must be callable.' );
			}
			if ( '' === trim( (string) $source_version ) ) {
				throw new InvalidArgumentException( 'The Pusula Lite source version is required.' );
			}

			$this->wpdb           = $wpdb;
			$this->option_reader  = $option_reader;
			$this->source_version = (string) $source_version;
			$this->clock          = is_callable( $clock ) ? $clock : static function () {
				return gmdate( 'Y-m-d\\TH:i:s\\Z' );
			};
		}

		/**
		 * Read and validate a complete export bundle from one consistent snapshot.
		 *
		 * @return array<string,mixed>
		 */
		public function build_bundle() {
			$this->begin_snapshot();

			try {
				$business_profile = $this->read_business_profile();
				$customers        = $this->read_customers();
				$contacts         = $this->read_contacts();
				$sales            = $this->read_sales();
				$installments     = $this->read_installments();
				$payments         = $this->read_payments();

				$this->validate_relationships( $customers, $contacts, $sales, $installments, $payments );

				$counts = array(
					'customers'   => count( $customers ),
					'contacts'    => count( $contacts ),
					'sales'       => count( $sales ),
					'installments' => count( $installments ),
					'payments'    => count( $payments ),
				);
				$totals = array(
					'sales_kurus'       => $this->sum_money_field( $sales, 'total_kurus', 'sales' ),
					'installments_kurus' => $this->sum_money_field( $installments, 'amount_kurus', 'installments' ),
					'payments_kurus'    => $this->sum_money_field( $payments, 'amount_kurus', 'payments' ),
				);

				$exported_at = (string) call_user_func( $this->clock );
				if ( ! preg_match( '/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$/', $exported_at ) ) {
					throw new RuntimeException( 'The export clock did not return a UTC RFC3339 timestamp.' );
				}

				$bundle = array(
					'format_version'  => self::FORMAT_VERSION,
					'source'          => self::SOURCE,
					'source_version'  => $this->source_version,
					'exported_at'     => $exported_at,
					'business_profile' => $business_profile,
					'customers'       => $customers,
					'contacts'        => $contacts,
					'sales'           => $sales,
					'installments'    => $installments,
					'payments'        => $payments,
					'manifest'        => array(
						'counts' => $counts,
						'totals' => $totals,
						'sha256' => '',
					),
				);

				$bundle['manifest']['sha256'] = hash( 'sha256', $this->encode_json( $bundle, false ) );
				$this->commit_snapshot();

				return $bundle;
			} catch ( Throwable $error ) {
				$this->rollback_snapshot();
				throw $error;
			}
		}

		/**
		 * Encode using the same compact UTF-8 representation used for the hash.
		 *
		 * @param array<string,mixed> $value  Value to encode.
		 * @param bool                $pretty Whether to pretty-print the JSON.
		 * @return string
		 */
		public function encode_json( array $value, $pretty = false ) {
			$flags = JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE;
			if ( defined( 'JSON_UNESCAPED_LINE_TERMINATORS' ) ) {
				$flags |= JSON_UNESCAPED_LINE_TERMINATORS;
			}
			if ( $pretty ) {
				$flags |= JSON_PRETTY_PRINT;
			}

			$json = json_encode( $value, $flags );
			if ( false === $json ) {
				throw new RuntimeException( 'JSON encoding failed: ' . json_last_error_msg() );
			}

			return $json;
		}

		/**
		 * Write a complete pretty JSON file via a temporary file and final rename.
		 *
		 * @param array<string,mixed> $bundle Bundle from build_bundle().
		 * @param string              $output Explicit destination path.
		 * @param bool                $force  Whether an existing file may be replaced.
		 * @return void
		 */
		public function write_bundle( array $bundle, $output, $force = false ) {
			$output = trim( (string) $output );
			if ( '' === $output || false !== strpos( $output, "\0" ) ) {
				throw new InvalidArgumentException( 'A valid explicit output path is required.' );
			}
			if ( is_dir( $output ) ) {
				throw new RuntimeException( 'The output path points to a directory: ' . $output );
			}
			if ( file_exists( $output ) && ! $force ) {
				throw new RuntimeException( 'The output file already exists. Use --force to replace it: ' . $output );
			}

			$directory = dirname( $output );
			if ( ! is_dir( $directory ) ) {
				throw new RuntimeException( 'The output directory does not exist: ' . $directory );
			}
			if ( ! is_writable( $directory ) ) {
				throw new RuntimeException( 'The output directory is not writable: ' . $directory );
			}

			$payload = $this->encode_json( $bundle, true ) . "\n";
			$temp    = tempnam( $directory, '.pusula-export-' );
			if ( false === $temp ) {
				throw new RuntimeException( 'Could not create a temporary export file in: ' . $directory );
			}

			$backup = null;
			try {
				$written = file_put_contents( $temp, $payload, LOCK_EX );
				if ( strlen( $payload ) !== $written ) {
					throw new RuntimeException( 'The complete export could not be written to the temporary file.' );
				}

				if ( file_exists( $output ) ) {
					if ( ! $force ) {
						throw new RuntimeException( 'The output file was created during export; refusing to overwrite it.' );
					}
					$backup = tempnam( $directory, '.pusula-export-old-' );
					if ( false === $backup || ! unlink( $backup ) || ! rename( $output, $backup ) ) {
						throw new RuntimeException( 'Could not stage the existing output file for safe replacement.' );
					}
				}

				if ( ! rename( $temp, $output ) ) {
					if ( null !== $backup && ! file_exists( $output ) ) {
						rename( $backup, $output );
						$backup = null;
					}
					throw new RuntimeException( 'Could not move the completed export into place: ' . $output );
				}

				$temp = null;
				if ( null !== $backup ) {
					if ( ! unlink( $backup ) ) {
						throw new RuntimeException( 'The export succeeded, but the replaced file backup could not be removed: ' . $backup );
					}
					$backup = null;
				}
			} finally {
				if ( null !== $temp && file_exists( $temp ) ) {
					unlink( $temp );
				}
				if ( null !== $backup && file_exists( $backup ) && ! file_exists( $output ) ) {
					rename( $backup, $output );
				}
			}
		}

		/**
		 * Convert a MySQL DECIMAL string to integer kuruş without floating point.
		 *
		 * @param mixed  $value Decimal value returned by wpdb.
		 * @param string $field Field label for diagnostics.
		 * @return int
		 */
		public static function decimal_to_kurus( $value, $field = 'money' ) {
			if ( is_int( $value ) ) {
				$value = (string) $value;
			}
			if ( ! is_string( $value ) || ! preg_match( '/^([+-]?)(\\d+)(?:\\.(\\d{1,2}))?$/', trim( $value ), $matches ) ) {
				throw new RuntimeException( 'Invalid DECIMAL value for ' . $field . '.' );
			}

			$negative = '-' === $matches[1];
			$whole    = ltrim( $matches[2], '0' );
			$whole    = '' === $whole ? '0' : $whole;
			$cents    = isset( $matches[3] ) ? str_pad( $matches[3], 2, '0' ) : '00';

			$max_whole = intdiv( PHP_INT_MAX - (int) $cents, 100 );
			if ( strlen( $whole ) > strlen( (string) $max_whole ) || ( strlen( $whole ) === strlen( (string) $max_whole ) && strcmp( $whole, (string) $max_whole ) > 0 ) ) {
				throw new RuntimeException( 'DECIMAL value is too large for integer kuruş: ' . $field . '.' );
			}

			$kurus = ( (int) $whole * 100 ) + (int) $cents;
			return $negative && 0 !== $kurus ? -$kurus : $kurus;
		}

		private function begin_snapshot() {
			$this->run_statement( 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ' );
			$this->run_statement( 'START TRANSACTION WITH CONSISTENT SNAPSHOT' );
			$this->snapshot_started = true;
		}

		private function commit_snapshot() {
			$this->run_statement( 'COMMIT' );
			$this->snapshot_started = false;
		}

		private function rollback_snapshot() {
			if ( $this->snapshot_started ) {
				$this->wpdb->query( 'ROLLBACK' );
				$this->snapshot_started = false;
			}
		}

		private function run_statement( $sql ) {
			$this->wpdb->last_error = '';
			$result = $this->wpdb->query( $sql );
			if ( false === $result || '' !== (string) $this->wpdb->last_error ) {
				throw new RuntimeException( 'Database statement failed: ' . $sql . '. ' . (string) $this->wpdb->last_error );
			}
		}

		private function read_rows( $table_suffix, $columns ) {
			$table = $this->wpdb->prefix . 'pusula_' . $table_suffix;
			$sql   = 'SELECT ' . $columns . ' FROM ' . $table . ' ORDER BY id ASC';

			$this->wpdb->last_error = '';
			$rows = $this->wpdb->get_results( $sql, ARRAY_A );
			if ( '' !== (string) $this->wpdb->last_error || ! is_array( $rows ) ) {
				throw new RuntimeException( 'Could not read ' . $table_suffix . '. ' . (string) $this->wpdb->last_error );
			}

			return $rows;
		}

		private function read_business_profile() {
			$stored = call_user_func( $this->option_reader, 'pusula_lite_business_profile', array() );
			$stored = is_array( $stored ) ? $stored : array();

			return array(
				'name'      => $this->string_value( $stored, 'name' ),
				'address'   => $this->string_value( $stored, 'address' ),
				'phone'     => $this->string_value( $stored, 'phone' ),
				'website'   => $this->string_value( $stored, 'website' ),
				'footer_sub' => $this->string_value( $stored, 'footer_sub' ),
			);
		}

		private function read_customers() {
			$rows   = $this->read_rows( 'customers', 'id, name, phone, address, work_address, notes, registration_date' );
			$result = array();
			foreach ( $rows as $row ) {
				$id       = $this->positive_id( $row, 'id', 'customer' );
				$result[] = array(
					'id'               => $id,
					'name'             => $this->string_value( $row, 'name' ),
					'phone'            => $this->string_value( $row, 'phone' ),
					'address'          => $this->string_value( $row, 'address' ),
					'work_address'     => $this->string_value( $row, 'work_address' ),
					'notes'            => $this->string_value( $row, 'notes' ),
					'registration_date' => $this->required_string( $row, 'registration_date', 'customer ' . $id ),
				);
			}
			return $result;
		}

		private function read_contacts() {
			$rows   = $this->read_rows( 'contacts', 'id, customer_id, name, phone, home_address, work_address' );
			$result = array();
			foreach ( $rows as $row ) {
				$id       = $this->positive_id( $row, 'id', 'contact' );
				$result[] = array(
					'id'          => $id,
					'customer_id' => $this->positive_id( $row, 'customer_id', 'contact ' . $id ),
					'name'        => $this->string_value( $row, 'name' ),
					'phone'       => $this->string_value( $row, 'phone' ),
					'home_address' => $this->string_value( $row, 'home_address' ),
					'work_address' => $this->string_value( $row, 'work_address' ),
				);
			}
			return $result;
		}

		private function read_sales() {
			$rows   = $this->read_rows( 'sales', 'id, customer_id, date, total, description, request_key' );
			$result = array();
			foreach ( $rows as $row ) {
				$id       = $this->positive_id( $row, 'id', 'sale' );
				$result[] = array(
					'id'          => $id,
					'customer_id' => $this->positive_id( $row, 'customer_id', 'sale ' . $id ),
					'date'        => $this->required_string( $row, 'date', 'sale ' . $id ),
					'total_kurus' => self::decimal_to_kurus( $this->required_value( $row, 'total', 'sale ' . $id ), 'sale ' . $id . ' total' ),
					'description' => $this->string_value( $row, 'description' ),
					'request_key' => $this->nullable_string( $row, 'request_key' ),
				);
			}
			return $result;
		}

		private function read_installments() {
			$rows   = $this->read_rows( 'installments', 'id, sale_id, due_date, amount, paid_date' );
			$result = array();
			foreach ( $rows as $row ) {
				$id       = $this->positive_id( $row, 'id', 'installment' );
				$result[] = array(
					'id'          => $id,
					'sale_id'     => $this->positive_id( $row, 'sale_id', 'installment ' . $id ),
					'due_date'    => $this->nullable_string( $row, 'due_date' ),
					'amount_kurus' => self::decimal_to_kurus( $this->required_value( $row, 'amount', 'installment ' . $id ), 'installment ' . $id . ' amount' ),
					'paid_date'   => $this->nullable_string( $row, 'paid_date' ),
				);
			}
			return $result;
		}

		private function read_payments() {
			$rows   = $this->read_rows( 'installment_payments', 'id, installment_id, amount, payment_date, created_at' );
			$result = array();
			foreach ( $rows as $row ) {
				$id       = $this->positive_id( $row, 'id', 'payment' );
				$result[] = array(
					'id'            => $id,
					'installment_id' => $this->positive_id( $row, 'installment_id', 'payment ' . $id ),
					'amount_kurus'  => self::decimal_to_kurus( $this->required_value( $row, 'amount', 'payment ' . $id ), 'payment ' . $id . ' amount' ),
					'payment_date'  => $this->required_string( $row, 'payment_date', 'payment ' . $id ),
					'created_at'    => $this->required_string( $row, 'created_at', 'payment ' . $id ),
				);
			}
			return $result;
		}

		private function validate_relationships( array $customers, array $contacts, array $sales, array $installments, array $payments ) {
			$customer_ids    = $this->unique_id_set( $customers, 'customers' );
			$sale_ids        = $this->unique_id_set( $sales, 'sales' );
			$installment_ids = $this->unique_id_set( $installments, 'installments' );
			$this->unique_id_set( $contacts, 'contacts' );
			$this->unique_id_set( $payments, 'payments' );

			foreach ( $contacts as $row ) {
				if ( ! isset( $customer_ids[ $row['customer_id'] ] ) ) {
					throw new RuntimeException( 'Contact ' . $row['id'] . ' references missing customer ' . $row['customer_id'] . '.' );
				}
			}
			foreach ( $sales as $row ) {
				if ( ! isset( $customer_ids[ $row['customer_id'] ] ) ) {
					throw new RuntimeException( 'Sale ' . $row['id'] . ' references missing customer ' . $row['customer_id'] . '.' );
				}
			}
			foreach ( $installments as $row ) {
				if ( ! isset( $sale_ids[ $row['sale_id'] ] ) ) {
					throw new RuntimeException( 'Installment ' . $row['id'] . ' references missing sale ' . $row['sale_id'] . '.' );
				}
			}
			foreach ( $payments as $row ) {
				if ( ! isset( $installment_ids[ $row['installment_id'] ] ) ) {
					throw new RuntimeException( 'Payment ' . $row['id'] . ' references missing installment ' . $row['installment_id'] . '.' );
				}
			}
		}

		private function unique_id_set( array $rows, $label ) {
			$ids = array();
			foreach ( $rows as $row ) {
				$id = $row['id'];
				if ( isset( $ids[ $id ] ) ) {
					throw new RuntimeException( 'Duplicate ' . $label . ' id ' . $id . '.' );
				}
				$ids[ $id ] = true;
			}
			return $ids;
		}

		private function sum_money_field( array $rows, $field, $label ) {
			$total = 0;
			foreach ( $rows as $row ) {
				$value = $row[ $field ];
				if ( ( $value > 0 && $total > PHP_INT_MAX - $value ) || ( $value < 0 && $total < PHP_INT_MIN - $value ) ) {
					throw new RuntimeException( 'The ' . $label . ' total exceeds the supported integer range.' );
				}
				$total += $value;
			}
			return $total;
		}

		private function positive_id( array $row, $key, $context ) {
			$value = $this->required_value( $row, $key, $context );
			$value = is_int( $value ) ? (string) $value : $value;
			if ( ! is_string( $value ) || ! preg_match( '/^[1-9]\\d*$/', $value ) ) {
				throw new RuntimeException( 'Invalid ' . $key . ' for ' . $context . '.' );
			}
			if ( strlen( $value ) > strlen( (string) PHP_INT_MAX ) || ( strlen( $value ) === strlen( (string) PHP_INT_MAX ) && strcmp( $value, (string) PHP_INT_MAX ) > 0 ) ) {
				throw new RuntimeException( 'The ' . $key . ' for ' . $context . ' exceeds the supported integer range.' );
			}
			return (int) $value;
		}

		private function required_value( array $row, $key, $context ) {
			if ( ! array_key_exists( $key, $row ) || null === $row[ $key ] ) {
				throw new RuntimeException( 'Missing ' . $key . ' for ' . $context . '.' );
			}
			return $row[ $key ];
		}

		private function required_string( array $row, $key, $context ) {
			$value = $this->required_value( $row, $key, $context );
			if ( ! is_scalar( $value ) || '' === (string) $value ) {
				throw new RuntimeException( 'Invalid ' . $key . ' for ' . $context . '.' );
			}
			return (string) $value;
		}

		private function string_value( array $row, $key ) {
			if ( ! array_key_exists( $key, $row ) || null === $row[ $key ] ) {
				return '';
			}
			if ( ! is_scalar( $row[ $key ] ) ) {
				throw new RuntimeException( 'Invalid string value for ' . $key . '.' );
			}
			return (string) $row[ $key ];
		}

		private function nullable_string( array $row, $key ) {
			if ( ! array_key_exists( $key, $row ) || null === $row[ $key ] ) {
				return null;
			}
			if ( ! is_scalar( $row[ $key ] ) ) {
				throw new RuntimeException( 'Invalid nullable string value for ' . $key . '.' );
			}
			return (string) $row[ $key ];
		}
	}
}

if ( ! class_exists( 'Pusula_Desktop_Export_Command' ) ) {
	/**
	 * Create a validated Pusula Desktop import bundle.
	 *
	 * ## OPTIONS
	 *
	 * --output=<path>
	 * : Explicit destination for the JSON bundle.
	 *
	 * [--dry-run]
	 * : Validate and print the manifest summary without writing a file.
	 *
	 * [--force]
	 * : Replace an existing output file after the new bundle is complete.
	 *
	 * ## EXAMPLES
	 *
	 *     wp --require=tools/pusula-desktop-export.php pusula desktop-export --output="C:\\secure\\pusula-desktop-export.json" --dry-run
	 *     wp --require=tools/pusula-desktop-export.php pusula desktop-export --output="C:\\secure\\pusula-desktop-export.json"
	 *
	 * @when after_wp_load
	 */
	class Pusula_Desktop_Export_Command {
		/**
		 * @param array<int,string>   $args       Positional arguments (unused).
		 * @param array<string,mixed> $assoc_args Named command arguments.
		 * @return void
		 */
		public function __invoke( $args, $assoc_args ) {
			unset( $args );
			try {
				if ( ! class_exists( 'Pusula_Lite_API' ) ) {
					throw new RuntimeException( 'Pusula Lite must be active before running the exporter.' );
				}
				if ( empty( $assoc_args['output'] ) ) {
					throw new InvalidArgumentException( 'The --output option is required.' );
				}

				global $wpdb;
				$exporter = new Pusula_Desktop_Legacy_Exporter(
					$wpdb,
					'get_option',
					Pusula_Lite_API::VERSION
				);
				$bundle   = $exporter->build_bundle();
				$dry_run = isset( $assoc_args['dry-run'] );
				$force   = isset( $assoc_args['force'] );

				$summary = array(
					'output' => (string) $assoc_args['output'],
					'dry_run' => $dry_run,
					'counts' => $bundle['manifest']['counts'],
					'totals' => $bundle['manifest']['totals'],
					'sha256' => $bundle['manifest']['sha256'],
				);
				WP_CLI::line( $exporter->encode_json( $summary, false ) );

				if ( $dry_run ) {
					WP_CLI::success( 'Dry run complete. No file was written.' );
					return;
				}

				$exporter->write_bundle( $bundle, $assoc_args['output'], $force );
				WP_CLI::success( 'Pusula Desktop export written to ' . $assoc_args['output'] );
			} catch ( Throwable $error ) {
				WP_CLI::error( $error->getMessage() );
			}
		}
	}
}

if ( defined( 'WP_CLI' ) && WP_CLI && class_exists( 'WP_CLI' ) ) {
	WP_CLI::add_command( 'pusula desktop-export', 'Pusula_Desktop_Export_Command' );
}
