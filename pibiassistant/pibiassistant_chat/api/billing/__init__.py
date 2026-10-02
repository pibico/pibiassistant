# pibiAssistant - Billing API package
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Billing endpoints: RETIRED.

PA Cloud was retired and AIDA runs natively, so billing no longer exists.
Every function is still re-exported here so the dotted whitelist path
``pibiassistant.pibiassistant_chat.api.billing.<func>`` keeps resolving for one
release and answers HTTP 410 (see ``pibiassistant.utils.retired``).
"""


from pibiassistant.pibiassistant_chat.api.billing.checkout import (
    initiate_plan_upgrade,
    reauthorize_mandate,
    verify_payment,
    verify_razorpay_credit_payment,
    verify_razorpay_payment,
)
from pibiassistant.pibiassistant_chat.api.billing.combined import (
    get_billing_details,
    get_billing_page_data,
    save_billing_details,
)
from pibiassistant.pibiassistant_chat.api.billing.credits import (
    get_consumption_breakdown,
    get_credit_balance,
    get_expiring_credits,
    purchase_credits,
)
from pibiassistant.pibiassistant_chat.api.billing.dashboard import (
    get_available_gateways,
    get_billing_dashboard,
    get_plan_options,
)
from pibiassistant.pibiassistant_chat.api.billing.hosted import (
    create_hosted_checkout,
)
from pibiassistant.pibiassistant_chat.api.billing.invoices import (
    download_invoice_pdf,
)
from pibiassistant.pibiassistant_chat.api.billing.pricing import (
    preview_plan_pricing,
    validate_promo_code,
)
from pibiassistant.pibiassistant_chat.api.billing.quota import (
    get_quota_status,
)
from pibiassistant.pibiassistant_chat.api.billing.seats import (
    add_user_seat,
    preview_seat_charge,
    remove_user_seat,
    verify_seat_payment,
)
from pibiassistant.pibiassistant_chat.api.billing.subscription import (
    cancel_scheduled_change,
    cancel_subscription,
    downgrade_to_free,
    get_billing_history,
    get_invoices,
    get_payment_instrument,
    get_payment_methods,
    get_subscription_status,
    get_usage_history,
    reactivate_subscription,
    update_payment_method,
)
from pibiassistant.pibiassistant_chat.api.billing.sync import (
    sync_subscription_status,
)
