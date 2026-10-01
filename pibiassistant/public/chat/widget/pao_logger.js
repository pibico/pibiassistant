/**
 * AIDA Widget Logger — Environment-aware logging for widget JS.
 *
 * Uses frappe.boot.developer_mode to detect environment.
 * Must be loaded AFTER pao_core.js (which sets up the AIDA namespace).
 *
 * Usage:
 *   PAOLogger.error('Payment failed:', err)   // always logs
 *   PAOLogger.warn('Token expiring')           // always logs
 *   PAOLogger.debug('Socket event:', data)     // dev only
 */
(function () {
	var noop = function () {};

	var isDev = function () {
		try {
			return Boolean(frappe.boot && frappe.boot.developer_mode);
		} catch (e) {
			return false;
		}
	};

	window.PAOLogger = {
		error: function () {
			// eslint-disable-next-line no-console
			console.error.apply(console, ["[AIDA]"].concat(Array.from(arguments)));
		},
		warn: function () {
			// eslint-disable-next-line no-console
			console.warn.apply(console, ["[AIDA]"].concat(Array.from(arguments)));
		},
		info: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.info.apply(console, ["[AIDA]"].concat(Array.from(arguments)));
			}
		},
		debug: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.log.apply(console, ["[AIDA]"].concat(Array.from(arguments)));
			}
		},
		log: function () {
			if (isDev()) {
				// eslint-disable-next-line no-console
				console.log.apply(console, ["[AIDA]"].concat(Array.from(arguments)));
			}
		},
	};
})();
