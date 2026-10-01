import { baseCall, getCall } from "../_core";

export const billing = {
	getDashboard: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_billing_dashboard"),

	getPageData: (params = {}) =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.get_billing_page_data",
			params
		),

	getPlans: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_plan_options"),

	getQuotaStatus: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_quota_status"),

	getAvailableGateways: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_available_gateways"),

	getBillingDetails: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_billing_details"),

	saveBillingDetails: (payload) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.save_billing_details",
			payload
		),

	previewPlanPricing: (plan, billingCycle = "monthly") =>
		getCall("pibiassistant.pibiassistant_chat.api.preview_plan_pricing", {
			plan,
			billing_cycle: billingCycle,
		}),

	previewSeatCharge: () =>
		getCall("pibiassistant.pibiassistant_chat.api.preview_seat_charge"),

	addUserSeat: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.add_user_seat"),

	// Payments are collected on the cloud service's own site, never here — a gateway
	// is onboarded against one declared address, and this app runs on a
	// different domain for every customer. Returns a one-shot checkout_url.
	createHostedCheckout: (purpose, params = {}, returnUrl = null) =>
		baseCall("pibiassistant.pibiassistant_chat.api.create_hosted_checkout", {
			purpose,
			params,
			return_url: returnUrl,
		}),

	removeUserSeat: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.remove_user_seat"),

	// Opens the PDF in a new tab — the backend streams it with
	// Content-Disposition: attachment, so the browser handles the
	// download automatically. Same-origin + session cookie, so no
	// JS blob dance needed.
	downloadInvoicePdf: (arInvoiceName) => {
		const url = `/api/method/pibiassistant.pibiassistant_chat.api.download_invoice_pdf?ar_invoice_name=${encodeURIComponent(
			arInvoiceName
		)}`;
		window.open(url, "_blank");
	},

	initiateUpgrade: (
		plan,
		billingCycle = "monthly",
		gateway = null,
		billingName = null,
		billingEmail = null,
		promoCode = null,
		paymentMethod = null
	) =>
		baseCall("pibiassistant.pibiassistant_chat.api.initiate_plan_upgrade", {
			plan,
			billing_cycle: billingCycle,
			gateway,
			billing_name: billingName,
			billing_email: billingEmail,
			promo_code: promoCode,
			payment_method: paymentMethod,
		}),

	verifyPayment: (sessionId) =>
		baseCall("pibiassistant.pibiassistant_chat.api.verify_payment", {
			session_id: sessionId,
		}),

	getInvoices: (limit = 10) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_invoices", {
			limit,
		}),

	syncSubscription: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.sync_subscription_status"),

	getUsageHistory: (days = 30) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_usage_history", {
			days,
		}),

	getPaymentMethods: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_payment_methods"),

	// The instrument on file for autopay, plus an `update_mode` of
	// "settle" | "swap" | "portal" telling the UI what the update button
	// will actually do. The backend decides; the UI renders one button.
	getPaymentInstrument: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_payment_instrument"),

	// Starts a checkout that changes the paying instrument. When a renewal
	// is unpaid it settles that invoice and saves the instrument in the same
	// authorization; otherwise it authorizes one currency unit and refunds
	// it. Stripe returns a portal URL instead.
	updatePaymentMethod: (paymentMethod = null, billingName = null) =>
		baseCall("pibiassistant.pibiassistant_chat.api.update_payment_method", {
			payment_method: paymentMethod,
			billing_name: billingName,
		}),

	// Re-authorize the saved Razorpay mandate without changing plans.
	// The upgrade endpoint rejects same-plan calls, so this dedicated
	// path goes straight to gateway checkout to mint a fresh token.
	// Surfaced when `subscription.needs_mandate_reauth` is set —
	// either the renewal cron's cap check fired or the bank cancelled
	// the saved token.
	reauthorizeMandate: (billingName = null, paymentMethod = null) =>
		baseCall("pibiassistant.pibiassistant_chat.api.reauthorize_mandate", {
			billing_name: billingName,
			payment_method: paymentMethod,
		}),

	cancelSubscription: (cancelImmediately = false) =>
		baseCall("pibiassistant.pibiassistant_chat.api.cancel_subscription", {
			cancel_immediately: cancelImmediately,
		}),

	reactivateSubscription: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.reactivate_subscription"),

	downgradeToFree: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.downgrade_to_free"),

	cancelScheduledChange: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.cancel_scheduled_change"),

	verifyRazorpayPayment: (paymentId, subscriptionId, signature) =>
		baseCall("pibiassistant.pibiassistant_chat.api.verify_razorpay_payment", {
			razorpay_payment_id: paymentId,
			razorpay_subscription_id: subscriptionId,
			razorpay_signature: signature,
		}),

	validatePromoCode: (code, plan) =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.billing.validate_promo_code",
			{
				promo_code: code,
				plan,
			}
		),

	// Prepaid credits
	getCreditBalance: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_credit_balance"),

	purchaseCredits: (creditAmount, gateway = null) =>
		baseCall("pibiassistant.pibiassistant_chat.api.purchase_credits", {
			credit_amount: creditAmount,
			gateway,
		}),

	getExpiringCredits: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_expiring_credits"),

	getConsumptionBreakdown: (days = 30) =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.get_consumption_breakdown",
			{
				days,
			}
		),

	verifyRazorpayCreditPayment: (paymentId, orderId, signature) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.verify_razorpay_credit_payment",
			{
				razorpay_payment_id: paymentId,
				razorpay_order_id: orderId,
				razorpay_signature: signature,
			}
		),

	// Verify a Razorpay seat-purchase payment after the widget closes.
	// Stripe seat purchases are confirmed via webhook, not this endpoint.
	verifySeatPayment: (paymentId, orderId, signature) =>
		baseCall("pibiassistant.pibiassistant_chat.api.verify_seat_payment", {
			razorpay_payment_id: paymentId,
			razorpay_order_id: orderId,
			razorpay_signature: signature,
		}),
};
