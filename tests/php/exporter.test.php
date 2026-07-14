<?php

if ( ! defined( 'ARRAY_A' ) ) {
	define( 'ARRAY_A', 'ARRAY_A' );
}

if ( ! defined( 'WP_CLI' ) ) {
	define( 'WP_CLI', true );
}

final class WP_CLI {
	public static $commands = array();
	public static $lines = array();
	public static $successes = array();

	public static function add_command( $name, $callable ) {
		self::$commands[ $name ] = $callable;
	}

	public static function line( $message ) {
		self::$lines[] = $message;
	}

	public static function success( $message ) {
		self::$successes[] = $message;
	}

	public static function error( $message ) {
		throw new RuntimeException( $message );
	}
}

final class Pusula_Lite_API {
	const VERSION = '1.3.6';
}

$pusula_exporter_test_profile = array();
function get_option( $name, $default = false ) {
	global $pusula_exporter_test_profile;
	return 'pusula_lite_business_profile' === $name ? $pusula_exporter_test_profile : $default;
}

require_once dirname( __DIR__, 2 ) . '/tools/pusula-desktop-export.php';

final class Pusula_Exporter_Fake_Wpdb {
	public $prefix = 'wp_';
	public $last_error = '';
	public $statements = array();
	public $selects = array();
	public $tables;

	public function __construct( array $tables ) {
		$this->tables = $tables;
	}

	public function query( $sql ) {
		$this->statements[] = $sql;
		return 1;
	}

	public function get_results( $sql, $format ) {
		$this->selects[] = $sql;
		if ( ARRAY_A !== $format || ! preg_match( '/ FROM wp_pusula_([a-z_]+) ORDER BY id ASC$/', $sql, $matches ) ) {
			$this->last_error = 'Unexpected test query';
			return null;
		}

		$table = $matches[1];
		if ( ! array_key_exists( $table, $this->tables ) ) {
			$this->last_error = 'Missing test table ' . $table;
			return null;
		}

		return $this->tables[ $table ];
	}
}

function pusula_exporter_fixture_tables() {
	return array(
		'customers' => array(
			array(
				'id' => '2', 'name' => 'Test Müşteri Ç', 'phone' => null, 'address' => 'Ev',
				'work_address' => 'İş', 'notes' => 'Not', 'registration_date' => '2026-01-02',
			),
			array(
				'id' => '7', 'name' => 'Örnek Müşteri', 'phone' => '555', 'address' => '',
				'work_address' => '', 'notes' => null, 'registration_date' => '2026-02-03',
			),
		),
		'contacts' => array(
			array(
				'id' => '4', 'customer_id' => '2', 'name' => 'Yakın', 'phone' => '123',
				'home_address' => null, 'work_address' => 'Ofis',
			),
		),
		'sales' => array(
			array(
				'id' => '10', 'customer_id' => '2', 'date' => '2026-03-04', 'total' => '12345678.90',
				'description' => 'Büyük satış', 'request_key' => null,
			),
			array(
				'id' => '11', 'customer_id' => '7', 'date' => '2026-03-05', 'total' => '0.10',
				'description' => null, 'request_key' => 'request-11',
			),
		),
		'installments' => array(
			array(
				'id' => '20', 'sale_id' => '10', 'due_date' => null, 'amount' => '0.05', 'paid_date' => null,
			),
		),
		'installment_payments' => array(
			array(
				'id' => '30', 'installment_id' => '20', 'amount' => '0.01',
				'payment_date' => '2026-03-06', 'created_at' => '2026-03-06 09:10:11',
			),
		),
	);
}

function pusula_exporter_create( Pusula_Exporter_Fake_Wpdb $wpdb ) {
	return new Pusula_Desktop_Legacy_Exporter(
		$wpdb,
		static function ( $name, $default ) {
			if ( 'pusula_lite_business_profile' !== $name ) {
				return $default;
			}
			return array(
				'name' => 'Enes Beko',
				'address' => 'Adana',
				'phone' => '0322',
				'website' => 'https://example.com/pusula',
				'footer_sub' => 'Kardeşler',
			);
		},
		'1.3.6',
		static function () {
			return '2026-07-14T12:34:56Z';
		}
	);
}

function pusula_exporter_assert_same( $expected, $actual, $message ) {
	if ( $expected !== $actual ) {
		throw new RuntimeException(
			$message . "\nExpected: " . var_export( $expected, true ) . "\nActual: " . var_export( $actual, true )
		);
	}
}

function pusula_exporter_assert_true( $condition, $message ) {
	if ( ! $condition ) {
		throw new RuntimeException( $message );
	}
}

function pusula_exporter_assert_throws( $callback, $message_fragment ) {
	try {
		call_user_func( $callback );
	} catch ( Throwable $error ) {
		if ( false === strpos( $error->getMessage(), $message_fragment ) ) {
			throw new RuntimeException( 'Unexpected exception: ' . $error->getMessage() );
		}
		return;
	}
	throw new RuntimeException( 'Expected exception containing: ' . $message_fragment );
}

$tests = array();

$tests['bundle matches desktop fields, ordering, totals, and checksum contract'] = static function () {
	$wpdb     = new Pusula_Exporter_Fake_Wpdb( pusula_exporter_fixture_tables() );
	$exporter = pusula_exporter_create( $wpdb );
	$bundle   = $exporter->build_bundle();

	pusula_exporter_assert_same(
		array( 'format_version', 'source', 'source_version', 'exported_at', 'business_profile', 'customers', 'contacts', 'sales', 'installments', 'payments', 'manifest' ),
		array_keys( $bundle ),
		'Top-level field order changed.'
	);
	pusula_exporter_assert_same( 1, $bundle['format_version'], 'Format version is wrong.' );
	pusula_exporter_assert_same( 'pusula-lite-wordpress', $bundle['source'], 'Source marker is wrong.' );
	pusula_exporter_assert_same( '1.3.6', $bundle['source_version'], 'Source version is wrong.' );
	pusula_exporter_assert_same( '2026-07-14T12:34:56Z', $bundle['exported_at'], 'UTC export timestamp is wrong.' );
	pusula_exporter_assert_same(
		array( 'name', 'address', 'phone', 'website', 'footer_sub' ),
		array_keys( $bundle['business_profile'] ),
		'Business-profile field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'id', 'name', 'phone', 'address', 'work_address', 'notes', 'registration_date' ),
		array_keys( $bundle['customers'][0] ),
		'Customer field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'id', 'customer_id', 'name', 'phone', 'home_address', 'work_address' ),
		array_keys( $bundle['contacts'][0] ),
		'Contact field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'id', 'customer_id', 'date', 'total_kurus', 'description', 'request_key' ),
		array_keys( $bundle['sales'][0] ),
		'Sale field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'id', 'sale_id', 'due_date', 'amount_kurus', 'paid_date' ),
		array_keys( $bundle['installments'][0] ),
		'Installment field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'id', 'installment_id', 'amount_kurus', 'payment_date', 'created_at' ),
		array_keys( $bundle['payments'][0] ),
		'Payment field order changed.'
	);
	pusula_exporter_assert_same( array( 'counts', 'totals', 'sha256' ), array_keys( $bundle['manifest'] ), 'Manifest field order changed.' );
	pusula_exporter_assert_same(
		array( 'customers', 'contacts', 'sales', 'installments', 'payments' ),
		array_keys( $bundle['manifest']['counts'] ),
		'Manifest count field order changed.'
	);
	pusula_exporter_assert_same(
		array( 'sales_kurus', 'installments_kurus', 'payments_kurus' ),
		array_keys( $bundle['manifest']['totals'] ),
		'Manifest total field order changed.'
	);
	pusula_exporter_assert_same( 1234567890, $bundle['sales'][0]['total_kurus'], 'Large DECIMAL conversion was not exact.' );
	pusula_exporter_assert_same( 1234567900, $bundle['manifest']['totals']['sales_kurus'], 'Sales total is wrong.' );
	pusula_exporter_assert_same( 5, $bundle['manifest']['totals']['installments_kurus'], 'Installment total is wrong.' );
	pusula_exporter_assert_same( 1, $bundle['manifest']['totals']['payments_kurus'], 'Payment total is wrong.' );
	pusula_exporter_assert_same( '', $bundle['customers'][0]['phone'], 'Nullable customer strings must become empty strings.' );
	pusula_exporter_assert_same( null, $bundle['sales'][0]['request_key'], 'Nullable request keys must remain null.' );
	pusula_exporter_assert_same( null, $bundle['installments'][0]['due_date'], 'Nullable dates must remain null.' );

	$expected_hash = $bundle['manifest']['sha256'];
	$bundle['manifest']['sha256'] = '';
	$compact = $exporter->encode_json( $bundle, false );
	pusula_exporter_assert_same( hash( 'sha256', $compact ), $expected_hash, 'Checksum did not use the empty sha256 field contract.' );
	pusula_exporter_assert_true( false !== strpos( $compact, 'Test Müşteri Ç' ), 'Compact JSON must contain unescaped UTF-8.' );
	pusula_exporter_assert_true( false !== strpos( $compact, 'https://example.com/pusula' ), 'Compact JSON must not escape slashes.' );
	pusula_exporter_assert_same(
		array( 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ', 'START TRANSACTION WITH CONSISTENT SNAPSHOT', 'COMMIT' ),
		$wpdb->statements,
		'Exporter did not use a committed consistent snapshot.'
	);
	$all_selects = implode( "\n", $wpdb->selects );
	pusula_exporter_assert_true( false === strpos( $all_selects, 'locks' ), 'Lock rows must not be selected.' );
	pusula_exporter_assert_true( false === strpos( $all_selects, 'users' ), 'WordPress users must not be selected.' );
};

$tests['money conversion is exact and rejects lossy values'] = static function () {
	pusula_exporter_assert_same( 0, Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( '0.00' ), 'Zero conversion failed.' );
	pusula_exporter_assert_same( 1, Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( '0.01' ), 'Cent conversion failed.' );
	pusula_exporter_assert_same( 1230, Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( '12.3' ), 'One-decimal conversion failed.' );
	pusula_exporter_assert_same( -5, Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( '-0.05' ), 'Negative conversion failed.' );
	pusula_exporter_assert_throws(
		static function () {
			Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( '1.001' );
		},
		'Invalid DECIMAL'
	);
	pusula_exporter_assert_throws(
		static function () {
			Pusula_Desktop_Legacy_Exporter::decimal_to_kurus( 1.25 );
		},
		'Invalid DECIMAL'
	);
};

$tests['orphan relationships fail and roll back before any file write'] = static function () {
	$cases = array(
		array( 'contacts', 0, 'customer_id', '999', 'Contact 4 references missing customer 999.' ),
		array( 'sales', 0, 'customer_id', '999', 'Sale 10 references missing customer 999.' ),
		array( 'installments', 0, 'sale_id', '999', 'Installment 20 references missing sale 999.' ),
		array( 'installment_payments', 0, 'installment_id', '999', 'Payment 30 references missing installment 999.' ),
	);

	foreach ( $cases as $case ) {
		$tables = pusula_exporter_fixture_tables();
		$tables[ $case[0] ][ $case[1] ][ $case[2] ] = $case[3];
		$wpdb = new Pusula_Exporter_Fake_Wpdb( $tables );

		pusula_exporter_assert_throws(
			static function () use ( $wpdb ) {
				pusula_exporter_create( $wpdb )->build_bundle();
			},
			$case[4]
		);
		pusula_exporter_assert_same( 'ROLLBACK', end( $wpdb->statements ), 'Invalid relationships must roll back the snapshot.' );
	}
};

$tests['writes are complete, overwrite-protected, and force-replaceable'] = static function () {
	$wpdb     = new Pusula_Exporter_Fake_Wpdb( pusula_exporter_fixture_tables() );
	$exporter = pusula_exporter_create( $wpdb );
	$bundle   = $exporter->build_bundle();
	$dir      = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'pusula-exporter-' . uniqid( '', true );
	$output   = $dir . DIRECTORY_SEPARATOR . 'bundle.json';

	if ( ! mkdir( $dir, 0700 ) ) {
		throw new RuntimeException( 'Could not create exporter test directory.' );
	}

	try {
		$exporter->write_bundle( $bundle, $output, false );
		$decoded = json_decode( file_get_contents( $output ), true );
		pusula_exporter_assert_same( $bundle, $decoded, 'Written bundle did not round-trip.' );

		$original = file_get_contents( $output );
		pusula_exporter_assert_throws(
			static function () use ( $exporter, $bundle, $output ) {
				$exporter->write_bundle( $bundle, $output, false );
			},
			'already exists'
		);
		pusula_exporter_assert_same( $original, file_get_contents( $output ), 'Protected output changed after refused overwrite.' );

		file_put_contents( $output, 'old export' );
		$exporter->write_bundle( $bundle, $output, true );
		pusula_exporter_assert_same( $bundle, json_decode( file_get_contents( $output ), true ), 'Forced replacement did not produce the complete bundle.' );
	} finally {
		if ( file_exists( $output ) ) {
			unlink( $output );
		}
		rmdir( $dir );
	}
};

$tests['WP-CLI command registers and dry-run prints summary without writing'] = static function () {
	global $wpdb, $pusula_exporter_test_profile;
	$wpdb = new Pusula_Exporter_Fake_Wpdb( pusula_exporter_fixture_tables() );
	$pusula_exporter_test_profile = array(
		'name' => 'Enes Beko', 'address' => 'Adana', 'phone' => '0322',
		'website' => 'https://example.com', 'footer_sub' => 'Kardeşler',
	);
	WP_CLI::$lines = array();
	WP_CLI::$successes = array();

	pusula_exporter_assert_same(
		'Pusula_Desktop_Export_Command',
		WP_CLI::$commands['pusula desktop-export'],
		'WP-CLI command was not registered.'
	);

	$output = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'pusula-dry-run-' . uniqid( '', true ) . '.json';
	$command = new Pusula_Desktop_Export_Command();
	$command(
		array(),
		array(
			'output' => $output,
			'dry-run' => true,
		)
	);

	pusula_exporter_assert_true( ! file_exists( $output ), 'Dry-run wrote an output file.' );
	pusula_exporter_assert_same( 1, count( WP_CLI::$lines ), 'Dry-run did not print one JSON summary.' );
	$summary = json_decode( WP_CLI::$lines[0], true );
	pusula_exporter_assert_same( true, $summary['dry_run'], 'Dry-run summary flag is wrong.' );
	pusula_exporter_assert_same( 2, $summary['counts']['customers'], 'Dry-run summary counts are wrong.' );
	pusula_exporter_assert_same(
		'Dry run complete. No file was written.',
		WP_CLI::$successes[0],
		'Dry-run completion message is wrong.'
	);
};

$failures = 0;
$number   = 0;
echo '1..' . count( $tests ) . PHP_EOL;
foreach ( $tests as $name => $test ) {
	++$number;
	try {
		call_user_func( $test );
		echo 'ok ' . $number . ' - ' . $name . PHP_EOL;
	} catch ( Throwable $error ) {
		++$failures;
		echo 'not ok ' . $number . ' - ' . $name . PHP_EOL;
		echo '# ' . str_replace( "\n", "\n# ", $error->getMessage() ) . PHP_EOL;
	}
}

exit( $failures > 0 ? 1 : 0 );
