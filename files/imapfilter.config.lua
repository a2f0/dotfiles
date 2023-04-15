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

thinkspan = IMAP {
    server = "imap.gmail.com",
    username = "dan@thinkspan.com",
    password = os.getenv("THINKSPAN_GMAIL_APP_SPECIFIC_PASSWORD"),
    ssl = "tls1"
}

mailboxes, folders = gmail:list_all('*')
print("=== mailboxes")
for _, m in ipairs(mailboxes) do print(m) end
print("=== folders")
for _, f in ipairs(folders) do print(f) end

-- Thinkspan
messages = thinkspan["INBOX"]:select_all()
messages:move_messages(gmail["INBOX"])

-- Alumni
messages = gmail["INBOX"]:contain_from("masters-alumni@cs.uchicago.edu")
messages:move_messages(gmail['[Gmail]/Trash'])

-- Amazon
messages = gmail["INBOX"]:contain_from('no-reply-aws@amazon.com')
messages:move_messages(gmail["Keep/Notifications/AWS"])
messages = gmail["INBOX"]:contain_from('payments-messages@amazon.com')
messages:move_messages(gmail["Keep/Notifications/Amazon"])
messages = gmail["INBOX"]:contain_from('no-reply@amazon.com')
messages:move_messages(gmail["Keep/Notifications/Amazon"])
messages = gmail["INBOX"]:contain_from('account-update@amazon.com')
messages:move_messages(gmail["Keep/Notifications/Amazon"])

-- AMC Theatres
messages = gmail["INBOX"]:contain_from('amctheaters.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- American Express
messages = gmail["INBOX"]:contain_from('americanexpress.com')
messages:move_messages(gmail["Keep/Notifications/American Express"])

-- Apple
messages = gmail["INBOX"]:contain_from('no_reply@email.apple.com')
messages:move_messages(gmail["Keep/Notifications/Apple"])
messages = gmail["INBOX"]:contain_from('developer@insideapple.apple.com')
messages:move_messages(gmail["Keep/Notifications/Apple"])

-- Axos
messages = gmail["INBOX"]:contain_from('axosbank.com')
messages:move_messages(gmail["Keep/Notifications/Axos"])

-- Azure
messages = gmail["INBOX"]:contain_from('azure-noreply@microsoft.com')
messages:move_messages(gmail["Keep/Notifications/Azure"])

-- BCBSIL
messages = gmail["INBOX"]:contain_from('BCBSIL_noreply@bcbsil.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Bitwarden
messages = gmail["INBOX"]:contain_from('bitwarden.com')
messages:move_messages(gmail["Keep/Notifications/Bitwarden"])

-- Box
messages = gmail["INBOX"]:contain_from('box.com')
messages:move_messages(gmail["Keep/Notifications/Box"])

-- Chase
messages = gmail["INBOX"]:contain_from('no-reply@alertsp.chase.com')
messages:move_messages(gmail["Keep/Notifications/Chase"])

-- Chipolte
messages = gmail["INBOX"]:contain_from('chipotle@email.chipotle.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Chattanooga Gas
messages = gmail["INBOX"]:contain_from('cgc@email.southerncompgas.com')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])
messages = gmail["INBOX"]:contain_from('noreply@speedpay.com'):contain_subject('Chattanooga Gas')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])
messages = gmail["INBOX"]:contain_from('cgc@emailweb.southerncompgas.com')
messages:move_messages(gmail["Keep/Notifications/Chattanooga Gas"])

-- CircleCI
messages = gmail["INBOX"]:contain_from('security@circleci.com')
messages:move_messages(gmail["Keep/Notifications/CircleCI"])

-- Coinbase
messages = gmail["INBOX"]:contain_from('coinbase.com')
messages:move_messages(gmail["Keep/Notifications/Coinbase"])

-- Computershare
messages = gmail["INBOX"]:contain_from('cpucommunications.com')
messages:move_messages(gmail["Keep/Notifications/Computershare"])
messages = gmail["INBOX"]:contain_from('computershare.com')
messages:move_messages(gmail["Keep/Notifications/Computershare"])

-- Confluence
messages = gmail["INBOX"]:contain_subject('[Confluence]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Confluence"])
messages = gmail["Keep/Confluence"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- CVS
messages = gmail["INBOX"]:contain_from('CVSPharmacy@pharmacy.cvs.com')
messages:move_messages(gmail["Keep/Notifications/CVS"])

-- Datadog
messages = gmail["INBOX"]:contain_from('datadog.com')
messages:move_messages(gmail["Keep/Notifications/Datadog"])
messages = gmail["INBOX"]:contain_from('datadoghq.com')
messages:move_messages(gmail["Keep/Notifications/Datadog"])

-- Dropbox
messages = gmail["INBOX"]:contain_from('no-reply@dropbox.com')
messages:move_messages(gmail["Keep/Notifications/CVS"])

-- Eastside Utility
messages = gmail["INBOX"]:contain_from('CustomerService@PaymentServiceNetwork.com')
messages:move_messages(gmail["Keep/Notifications/Eastside Utility"])
messages = gmail["INBOX"]:contain_from('no-reply@invoicecloud.net')
messages:move_messages(gmail["Keep/Notifications/Eastside Utility"])

-- eBay
messages = gmail["INBOX"]:contain_from('ebay.com')
messages:move_messages(gmail["Keep/Notifications/eBay"])

-- EPB
messages = gmail["INBOX"]:contain_from('customer.service@epb.net')
messages:move_messages(gmail["Keep/Notifications/EPB"])

-- Experian
messages = gmail["INBOX"]:contain_from('experian.com')
messages:move_messages(gmail["Keep/Notifications/Experian"])
messages = gmail["Keep/Notifications/Experian"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Farmers Insurance
messages = gmail["INBOX"]:contain_from('noreply@policy.farmers.com')
messages:move_messages(gmail["Keep/Notifications/Farmers"])

-- Flynn's Barber Studio
messages = gmail["INBOX"]:contain_subject('Barber Studio')
messages:move_messages(gmail["[Gmail]/Trash"])

-- Jira
messages = gmail["INBOX"]:contain_subject('[JIRA]'):contain_from('atlassian.net')
messages:move_messages(gmail["Keep/Jira"])
messages = gmail["INBOX"]:contain_from('no-reply@spartez-software.com')
messages:move_messages(gmail["Keep/Jira"])
messages = gmail["Keep/Jira"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Gemini
messages = gmail["INBOX"]:contain_from("hello@news.gemini.com")
messages:move_messages(gmail["Keep/GitHub"])
messages = gmail["INBOX"]:contain_from("no-reply@em.gemini.com")
messages:move_messages(gmail["Keep/GitHub"])

-- GitHub
messages = gmail["INBOX"]:contain_from("github.com")
messages:move_messages(gmail["Keep/GitHub"])
messages = gmail["Keep/GitHub"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])

-- Google
messages = gmail["INBOX"]:contain_from('payments-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])
messages = gmail["INBOX"]:contain_from('firebase-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])
messages = gmail["INBOX"]:contain_from('noreply-local-guides@google.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('workspace-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])
messages = gmail["INBOX"]:contain_from('voice-noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('no-reply@accounts.google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('googledev-noreply@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])
messages = gmail["INBOX"]:contain_from('googleplay-developer-support@google.com')
messages:move_messages(gmail["Keep/Notifications/Google"])
messages = gmail["INBOX"]:contain_from('noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('drive-shares-dm-noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('comments-noreply@docs.google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('CloudPlatform-noreply@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])
messages = gmail["INBOX"]:contain_from('noreply-play-developer-console@google.com')
messages:move_messages(gmail["[Gmail]/Trash"])

-- Home Depot
messages = gmail["INBOX"]:contain_from('homedepot.com')
messages:move_messages(gmail["Keep/Notifications/Home Depot"])


-- Heroku
messages = gmail["INBOX"]:contain_from('bot@notifications.heroku.com')
messages:move_messages(gmail["Keep/Notifications/Heroku"])
messages = gmail["Keep/Notifications/Heroku"]:is_older(30)
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('team.notifications@herokumanager.com')
messages:move_messages(gmail["Keep/Notifications/Heroku"])

-- Intuit
messages = gmail["INBOX"]:contain_from('intuit@notifications.intuit.com')
messages:move_messages(gmail["Keep/Notifications/Intuit"])

-- Lawn Starter
messages = gmail["INBOX"]:contain_from('lawnstarter.com')
messages:move_messages(gmail["Keep/Notifications/Lawn Starter"])

-- LinkedIn
messages = gmail["INBOX"]:contain_from('messages-noreply@linkedin.com')
messages:move_messages(gmail["Keep/Notifications/LinkedIn"])

-- Lowe's
messages = gmail["INBOX"]:contain_from('do-not-reply@notifications.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@confirmation.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])
messages = gmail["INBOX"]:contain_from('do-not-reply@receipt.lowes.com')
messages:move_messages(gmail["Keep/Notifications/Lowe's"])

-- Open AI
messages = gmail["INBOX"]:contain_from('noreply@email.openai.com')
messages:move_messages(gmail["Keep/Notifications/Open AI"])

-- OnPay
messages = gmail["INBOX"]:contain_from('onpay.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- PayPal
messages = gmail["INBOX"]:contain_from('service@paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])
messages = gmail["INBOX"]:contain_from('paypal@mail.paypal.com')
messages:move_messages(gmail["Keep/Notifications/PayPal"])

-- Schwab
messages = gmail["INBOX"]:contain_from('schwab.com')
messages:move_messages(gmail["Keep/Notifications/Schwab"])

-- Spectrum Emails
messages = gmail["INBOX"]:contain_from('spectrumemails.com')
messages:move_messages(gmail["Keep/Notifications/Spectrum"])

-- TD Ameritrade
messages = gmail["INBOX"]:contain_from('client@notifications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])
messages = gmail["INBOX"]:contain_from('from@communications.tdameritrade.com')
messages:move_messages(gmail["Keep/Notifications/TD Ameritrade"])

-- tZERO
messages = gmail["INBOX"]:contain_from('tzero.com')
messages:move_messages(gmail["Keep/Notifications/tZERO"])

-- Slack
messages = gmail["INBOX"]:contain_from('slack.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('slackhq.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Starbucks
messages = gmail["INBOX"]:contain_from('starbucks.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Twilio
messages = gmail["INBOX"]:contain_from('twilio.com')
messages:move_messages(gmail["Keep/Notifications/Twilio"])

-- Thinkspan
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspanstaging.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('postmaster@send.thinkspan.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('appfire.com') -- Sprint Estimation
messages:move_messages(gmail['[Gmail]/Trash'])

-- UPS
messages = gmail["INBOX"]:contain_from('ups.com')
messages:move_messages(gmail["Keep/Notifications/UPS"])

-- Venmo
messages = gmail["INBOX"]:contain_from('venmo.com')
messages:move_messages(gmail["Keep/Notifications/Venmo"])

-- Walmart
messages = gmail["INBOX"]:contain_from('walmart.com')
messages:move_messages(gmail["Keep/Notifications/Walmart"])

-- YouVersion
messages = gmail["INBOX"]:contain_from('youversion.com')
messages:move_messages(gmail['[Gmail]/Trash'])

-- Webull
messages = gmail["INBOX"]:contain_from('webull.com')
messages:move_messages(gmail["Keep/Notifications/Webull"])
messages = gmail["INBOX"]:contain_from('uscl_stmt_mbox@investordelivery.com')
messages:move_messages(gmail["Keep/Notifications/Webull"])

-- Sent
messages = gmail["[Gmail]/Sent Mail"]:is_older(1095)
messages:move_messages(gmail['[Gmail]/Trash'])

-- From Me
messages = gmail["INBOX"]:contain_from('dansullivan@gmail.com')
messages:move_messages(gmail['[Gmail]/Trash'])
messages = gmail["INBOX"]:contain_from('dan@thinkspan.com')
messages:move_messages(gmail['[Gmail]/Trash'])
