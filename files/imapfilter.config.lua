options.timeout = 1200
options.create = true
options.subscribe = true
options.expunge = true

gmail = IMAP {
    server = "imap.gmail.com",
    username = "dansullivan@gmail.com",
    password = os.getenv("GMAIL_APP_SPECIFIC_PASSWORD"),
    ssl = "tls1"
}

accounts = {
    {name = "gmail", account = gmail}
}

-- Helper function to process email filters
local function process_filter(account, from_folder, from_address, to_folder, subject_pattern, body_pattern)
    local messages
    if from_address then
        messages = account[from_folder]:contain_from(from_address)
    elseif subject_pattern and body_pattern then
        messages = account[from_folder]:match_subject(subject_pattern):match_body(body_pattern)
    elseif subject_pattern then
        messages = account[from_folder]:match_subject(subject_pattern)
    end
    if messages then
        messages:move_messages(account[to_folder])
    end
end

-- Helper function to clean old messages from a folder
local function clean_old_messages(account, folder, days)
    local messages = account[folder]:is_older(days)
    messages:move_messages(account['[Gmail]/Trash'])
end

-- Helper function to apply filters to an account
local function apply_filters(account, filters)
    for _, filter in ipairs(filters) do
        process_filter(account, "INBOX", filter.from, filter.to, filter.subject, filter.body)

        if filter.clean_days and filter.to ~= '[Gmail]/Trash' then
            clean_old_messages(account, filter.to, filter.clean_days)
        end
    end
end

-- Define filter rules for both accounts
local common_filters = {
    -- GitHub
    {from = "github.com", to = "Keep/Notifications/GitHub", clean_days = 30},

    -- Heroku
    {from = 'bot@notifications.heroku.com', to = "Keep/Notifications/Heroku", clean_days = 30},
    {from = 'team.notifications@herokumanager.com', to = "Keep/Notifications/Heroku"},
    {from = 'noreply@salesforce.com', to = "Keep/Notifications/Heroku"},
    {from = 'noreply@heroku.com', to = "Keep/Notifications/Heroku"},

    -- Atlassian
    {from = 'am.atlassian.com', to = "Keep/Notifications/Atlassian", clean_days = 30},
    {from = 'info@e.atlassian.com', to = "Keep/Notifications/Atlassian"},

    -- Google
    {from = 'payments-noreply@google.com', to = "Keep/Notifications/Google"},
    {from = 'firebase-noreply@google.com', to = "Keep/Notifications/Google"},
    {from = 'noreply-local-guides@google.com', to = '[Gmail]/Trash'},
    {from = 'workspace-noreply@google.com', to = "Keep/Notifications/Google"},
    {from = 'voice-noreply@google.com', to = "[Gmail]/Trash"},
    {from = 'no-reply@accounts.google.com', to = '[Gmail]/Trash'},
    {from = 'googledev-noreply@google.com', to = "Keep/Notifications/Google"},
    {from = 'googleplay-developer-support@google.com', to = "Keep/Notifications/Google"},
    {from = 'noreply@google.com', to = '[Gmail]/Trash'},
    {from = 'drive-shares-dm-noreply@google.com', to = '[Gmail]/Trash'},
    {from = 'comments-noreply@docs.google.com', to = '[Gmail]/Trash'},
    {from = 'CloudPlatform-noreply@google.com', to = '[Gmail]/Trash'},
    {from = 'noreply-play-developer-console@google.com', to = '[Gmail]/Trash'},
    {from = 'calendar-noreply@google.com', to = '[Gmail]/Trash'},
    {subject = '^Invitation: ', body = 'https://calendar.google.com/calendar', to = "Keep/Notifications/Google"},
    {subject = '^Updated invitation:', body = 'https://calendar.google.com/calendar', to = "Keep/Notifications/Google"},
    {subject = '^Canceled event:', body = 'https://calendar.google.com/calendar', to = "Keep/Notifications/Google"},
    {subject = '^Canceled event with note:', body = 'https://calendar.google.com/calendar', to = "Keep/Notifications/Google"},
    {subject = '^Accepted: ', body = 'https://calendar.google.com/calendar', to = "Keep/Notifications/Google"},

    -- Facebook
    {from = 'advertise-noreply@support.facebook.com', to = "Keep/Notifications/Facebook"},
    {from = 'facebookmail.com', to = "Keep/Notifications/Facebook"},
    {from = 'developers.facebook.com', to = "Keep/Notifications/Facebook"},

    -- Apple
    {from = 'no_reply@email.apple.com', to = "Keep/Notifications/Apple", clean_days = 30},
    {from = 'developer@insideapple.apple.com', to = "Keep/Notifications/Apple"},
    {from = 'apple_ads@insideapple.apple.com', to = "Keep/Notifications/Apple"},
    {from = 'searchads@insideapple.apple.com', to = "Keep/Notifications/Apple"},

    -- From Me
    {from = 'dansullivan@gmail.com', to = '[Gmail]/Trash'},

    -- Zoom
    {subject = '^Please join Zoom meeting in progress', to = '[Gmail]/Trash'},
    {from = 'no-reply@zoom.us', to = '[Gmail]/Trash'},

    -- Sentry
    {from = 'noreply@md.getsentry.com', to = "Keep/Notifications/Sentry", clean_days = 30},
    {from = 'updates@sentry.io', to = "Keep/Notifications/Sentry"},
    {from = 'learn@sentry.io', to = "Keep/Notifications/Sentry"},
    {from = 'help@sentry.io', to = "Keep/Notifications/Sentry"},
    {from = 'support@sentry.io', to = "Keep/Notifications/Sentry"},

    -- Twilio
    {from = 'twilio.com', to = "Keep/Notifications/Twilio"},

    -- Airtable
    {from = 'airtable.com', to = "Keep/Notifications/Airtable"},

    -- Slack
    {from = 'slack.com', to = '[Gmail]/Trash'},
    {from = 'slackhq.com', to = '[Gmail]/Trash'},

    -- OpenAI
    {from = 'openai.com', to = '[Gmail]/Trash'},

    -- Notion
    {from = 'notion.io', to = '[Gmail]/Trash'},

    -- Bitwarden
    {from = 'bitwarden.com', to = '[Gmail]/Trash'},

    -- MongoDB
    {from = 'cloud-manager-support@mongodb.com', to = '[Gmail]/Trash'},
    {from = 'mongodb@alerts.mongodb.com', to = '[Gmail]/Trash'},

    -- ClickUp
    {from = 'notifications@tasks.clickup.com', to = '[Gmail]/Trash'},

    -- Stripe
    {from = 'stripe.com', to = '[Gmail]/Trash'},

    -- Hubspot
    {from = 'hubspot.com', to = '[Gmail]/Trash'},

    -- SunIP (duplicate move fixed)
    {from = 'sunip.com', to = "Keep/Notifications/SunIP"},

    -- Telnyx (duplicate move fixed)
    {from = 'telnyx.com', to = "Keep/Notifications/Telnyx"},
}

-- Process filters for all accounts
for _, acc in ipairs(accounts) do
    local account = acc.account
    local account_name = acc.name

    print("Processing filters for account: " .. account_name)

    -- Apply common filters
    apply_filters(account, common_filters)
end

--
-- Gmail personal account specific filters
--
local gmail_filters = {
    -- Alumni
    {from = "masters-alumni@cs.uchicago.edu", to = '[Gmail]/Trash'},

    -- Amazon
    {from = 'no-reply-aws@amazon.com', to = "Keep/Notifications/AWS"},
    {from = 'payments-messages@amazon.com', to = "Keep/Notifications/Amazon"},
    {from = 'no-reply@amazon.com', to = "Keep/Notifications/Amazon"},
    {from = 'account-update@amazon.com', to = "Keep/Notifications/Amazon"},
    {from = 'order-update@amazon.com', to = "Keep/Notifications/Amazon"},

    -- AMC Theatres
    {from = 'amctheaters.com', to = '[Gmail]/Trash'},

    -- American Express
    {from = 'americanexpress.com', to = "Keep/Notifications/American Express"},

    -- Axos
    {from = 'axosbank.com', to = "Keep/Notifications/Axos"},

    -- Azure
    {from = 'azure-noreply@microsoft.com', to = "Keep/Notifications/Azure"},

    -- BCBSIL
    {from = 'BCBSIL_noreply@bcbsil.com', to = '[Gmail]/Trash'},

    -- Box
    {from = 'box.com', to = "Keep/Notifications/Box"},

    -- Chase
    {from = 'no.reply.alerts@chase.com', to = "Keep/Notifications/Chase"},

    -- Chipotle
    {from = 'chipotle@email.chipotle.com', to = '[Gmail]/Trash'},

    -- Chattanooga Gas
    {from = 'cgc@email.southerncompgas.com', to = "Keep/Notifications/Chattanooga Gas"},
    {from = 'cgc@emailweb.southerncompgas.com', to = "Keep/Notifications/Chattanooga Gas"},

    -- CircleCI
    {from = 'circleci.com', to = '[Gmail]/Trash'},

    -- Coinbase
    {from = 'coinbase.com', to = "Keep/Notifications/Coinbase"},

    -- Computershare
    {from = 'cpucommunications.com', to = "Keep/Notifications/Computershare"},
    {from = 'computershare.com', to = "Keep/Notifications/Computershare"},

    -- CVS
    {from = 'CVSPharmacy@pharmacy.cvs.com', to = "Keep/Notifications/CVS"},

    -- Datadog
    {from = 'datadog.com', to = "Keep/Notifications/Datadog"},
    {from = 'datadoghq.com', to = "Keep/Notifications/Datadog"},

    -- Dropbox (fixed target folder)
    {from = 'no-reply@dropbox.com', to = "Keep/Notifications/Dropbox"},

    -- Eastside Utility
    {from = 'CustomerService@PaymentServiceNetwork.com', to = "Keep/Notifications/Eastside Utility"},
    {from = 'no-reply@invoicecloud.net', to = "Keep/Notifications/Eastside Utility"},

    -- eBay
    {from = 'ebay.com', to = "Keep/Notifications/eBay"},

    -- EPB
    {from = 'customer.service@epb.net', to = "Keep/Notifications/EPB"},

    -- Experian
    {from = 'experian.com', to = "Keep/Notifications/Experian", clean_days = 30},

    -- Farmers Insurance
    {from = 'noreply@policy.farmers.com', to = "Keep/Notifications/Farmers"},

    -- Figma
    {from = 'figma.com', to = "Keep/Notifications/Figma"},

    -- Firefox
    {from = 'firefox.com', to = "[Gmail]/Trash"},

    -- GEICO
    {from = 'geico.com', to = "[Gmail]/Trash"},

    -- Gemini (fixed target folder)
    {from = "hello@news.gemini.com", to = "Keep/Notifications/Gemini"},
    {from = "no-reply@em.gemini.com", to = "Keep/Notifications/Gemini"},

    -- Home Depot
    {from = 'homedepot.com', to = "Keep/Notifications/Home Depot"},

    -- Intuit
    {from = 'intuit@notifications.intuit.com', to = "Keep/Notifications/Intuit"},

    -- Lawn Starter
    {from = 'lawnstarter.com', to = "Keep/Notifications/Lawn Starter"},

    -- LinkedIn
    {from = 'messages-noreply@linkedin.com', to = "Keep/Notifications/LinkedIn"},

    -- Lowe's
    {from = 'do-not-reply@notifications.lowes.com', to = "Keep/Notifications/Lowe's"},
    {from = 'do-not-reply@confirmation.lowes.com', to = "Keep/Notifications/Lowe's"},
    {from = 'do-not-reply@receipt.lowes.com', to = "Keep/Notifications/Lowe's"},

    -- Mailgun
    {from = 'mailgun.com', to = "Keep/Notifications/Mailgun"},
    {from = 'support@mailgun.net', to = "Keep/Notifications/Mailgun"},

    -- Miro
    {from = 'miro.com', to = "Keep/Notifications/Miro", clean_days = 30},

    -- MongoDB
    {from = 'mongodb.com', to = "Keep/Notifications/MongoDB"},

    -- Open AI
    {from = 'noreply@email.openai.com', to = "Keep/Notifications/Open AI"},

    -- OnPay
    {from = 'onpay.com', to = '[Gmail]/Trash'},

    -- PayPal
    {from = 'service@paypal.com', to = "Keep/Notifications/PayPal"},
    {from = 'paypal@mail.paypal.com', to = "Keep/Notifications/PayPal"},

    -- Safeco
    {from = 'email-safeco.com', to = "Keep/Notifications/Safeco"},

    -- Schwab
    {from = 'schwab.com', to = "Keep/Notifications/Schwab"},

    -- Spectrum Emails
    {from = 'spectrumemails.com', to = "Keep/Notifications/Spectrum"},

    -- Spotify
    {from = 'spotify.com', to = '[Gmail]/Trash'},

    -- TD Ameritrade
    {from = 'client@notifications.tdameritrade.com', to = "Keep/Notifications/TD Ameritrade"},
    {from = 'from@communications.tdameritrade.com', to = "Keep/Notifications/TD Ameritrade"},

    -- Test Fairy
    {subject = '^Tester feedback report for', to = "Keep/Notifications/TestFairy"},
    {subject = '^New build of', to = "Keep/Notifications/TestFairy"},

    -- Trashbilling.com
    {from = 'trashbilling.com', to = '[Gmail]/Trash'},

    -- tZERO
    {from = 'tzero.com', to = "Keep/Notifications/tZERO"},

    -- Starbucks
    {from = 'starbucks.com', to = '[Gmail]/Trash'},

    -- UPS
    {from = 'ups.com', to = "Keep/Notifications/UPS"},

    -- Venmo
    {from = 'venmo.com', to = "Keep/Notifications/Venmo"},

    -- Walmart
    {from = 'walmart.com', to = "Keep/Notifications/Walmart"},

    -- YouVersion
    {from = 'youversion.com', to = '[Gmail]/Trash'},

    -- Webull
    {from = 'webull.com', to = "Keep/Notifications/Webull"},
    {from = 'uscl_stmt_mbox@investordelivery.com', to = "Keep/Notifications/Webull"},

    -- Workable
    {from = 'noreply@workablemail.com', to = '[Gmail]/Trash'},
}

-- Apply Gmail-specific filters
apply_filters(gmail, gmail_filters)

-- Special cases
-- Chattanooga Gas with subject filter
local messages = gmail["INBOX"]:contain_from('noreply@speedpay.com'):contain_subject('Chattanooga Gas')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])

-- Confluence
messages = gmail["INBOX"]:contain_subject('[Confluence]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Notifications/Confluence"])
clean_old_messages(gmail, "Keep/Notifications/Confluence", 30)

-- Jira
messages = gmail["INBOX"]:contain_subject('[JIRA]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Notifications/Jira"])
process_filter(gmail, "INBOX", 'no-reply@spartez-software.com', "Keep/Notifications/Jira")
clean_old_messages(gmail, "Keep/Notifications/Jira", 30)

-- List mailboxes
mailboxes, folders = gmail:list_all('*')
print("=== mailboxes")
for _, m in ipairs(mailboxes) do print(m) end
print("=== folders")
for _, f in ipairs(folders) do print(f) end

-- Clean old sent mail
messages = gmail["[Gmail]/Sent Mail"]:is_older(1095)
messages:move_messages(gmail['[Gmail]/Trash'])
