from pyspark import pipelines as dp
from pyspark.sql.dataframe import DataFrame
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(to_email, subject, body, from_email, app_password):
    """Sends an email using Gmail SMTP server."""
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)


def create_fraud_alert_email_body(alert_data):
    """Creates the HTML email body for a fraud card alert."""
    return f"""<html><body style="font-family: Arial, sans-serif;">
<h2 style="color: #dc3545; background-color: #f8d7da; padding: 15px; border-radius: 5px;">🚨 FRAUD ALERT - IMMEDIATE ACTION REQUIRED</h2>
<p>Dear {alert_data['customer_name']},</p>
<p style="color: #721c24; font-weight: bold;">We have detected a FRAUDULENT transaction on your account that matches our fraud watchlist.</p>
<div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #dc3545; margin: 20px 0;">
<h3 style="margin-top: 0; color: #721c24;">⚠️ Fraud Details</h3>
<ul style="list-style-type: none; padding-left: 0;">
<li><strong>Risk Level:</strong> <span style="color: #dc3545;">{alert_data['risk_level']}</span></li>
<li><strong>Watch Type:</strong> {alert_data['watch_type']}</li>
<li><strong>Reason:</strong> {alert_data['reason_description']}</li>
<li><strong>Recommended Action:</strong> <span style="color: #dc3545;">{alert_data['action']}</span></li>
</ul></div>
<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #6c757d; margin: 20px 0;">
<h3 style="margin-top: 0;">Transaction Details</h3>
<ul style="list-style-type: none; padding-left: 0;">
<li><strong>Transaction ID:</strong> {alert_data['transaction_id']}</li>
<li><strong>Card Number:</strong> ****{alert_data['card_last4']}</li>
<li><strong>Amount:</strong> {alert_data['currency']} {alert_data['amount']:,.2f}</li>
<li><strong>Merchant:</strong> {alert_data['merchant_name']} ({alert_data['merchant_category']})</li>
<li><strong>Location:</strong> {alert_data['transaction_city']}, {alert_data['transaction_country']}</li>
<li><strong>Date/Time:</strong> {alert_data['transaction_timestamp']}</li>
<li><strong>Payment Channel:</strong> {alert_data['payment_channel']}</li>
{"<li><strong>International Transaction:</strong> Yes</li>" if alert_data['is_international'] else ""}
</ul></div>
<div style="background-color: #d1ecf1; padding: 15px; border-left: 4px solid #0c5460; margin: 20px 0;">
<h3 style="margin-top: 0; color: #0c5460;">🔒 IMMEDIATE ACTIONS REQUIRED:</h3>
<ol>
<li><strong style="color: #dc3545;">DO NOT authorize this transaction if you did not make it</strong></li>
<li>Call our fraud department immediately at <strong>1-800-FRAUD-HELP</strong></li>
<li>Block your card through our mobile app or website</li>
<li>Review all recent transactions for additional suspicious activity</li>
</ol></div>
<p style="font-weight: bold; color: #721c24;">This alert was generated based on fraud intelligence from: {alert_data['reported_source']}</p>
<hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
<p style="font-size: 12px; color: #6c757d;">
Alert ID: {alert_data['alert_id']}<br>
Watchlist ID: {alert_data['watchlist_id']}<br>
Reason Code: {alert_data['reason_code']}<br>
Reported By: {alert_data['reported_by']}<br>
This is an automated FRAUD alert from FinGuard Fraud Detection System.
</p>
</body></html>"""


# Get configuration outside the foreach_batch_sink for serialization
EMAIL_FROM = "pratikstha278@gmail.com"
try:
    APP_PASSWORD = dbutils().secrets().get("finguard-scope", "gmail_api_key")
except Exception as e:
    print(f"❌ Failed to retrieve Gmail API key from secrets: {e}")
    APP_PASSWORD = None


@dp.foreach_batch_sink(name="fraud_email_notifier_sink")
def send_fraud_card_alert_emails(df, batch_id):
    """ForEachBatch sink that sends email alerts for fraud card transactions."""
    
    if APP_PASSWORD is None:
        print(f"❌ Batch {batch_id}: Gmail API key not available, skipping email notifications")
        return
    
    rows = df.collect()
    print(f"🚨 Batch {batch_id}: Processing {len(rows)} FRAUD alert(s)...")
    
    success_count = 0
    failure_count = 0
    
    for row in rows:
        try:
            # Extract last 4 digits of card number for display
            card_last4 = str(row.card_number)[-4:] if row.card_number else "XXXX"
            
            alert_data = {
                'alert_id': row.alert_id,
                'customer_name': row.customer_name,
                'transaction_id': row.transaction_id,
                'card_last4': card_last4,
                'amount': float(row.amount),
                'currency': row.currency,
                'merchant_name': row.merchant_name,
                'merchant_category': row.merchant_category,
                'transaction_timestamp': str(row.transaction_timestamp),
                'transaction_city': row.transaction_city,
                'transaction_country': row.transaction_country,
                'payment_channel': row.payment_channel,
                'is_international': row.is_international,
                'watchlist_id': row.watchlist_id,
                'watch_type': row.watch_type,
                'risk_level': row.risk_level,
                'action': row.action,
                'reason_code': row.reason_code,
                'reason_description': row.reason_description,
                'reported_by': row.reported_by,
                'reported_source': row.reported_source
            }
            
            subject = f"🚨 FRAUD ALERT - Card Transaction Flagged - {alert_data['alert_id']}"
            body = create_fraud_alert_email_body(alert_data)
            
            send_email(row.customer_email, subject, body, EMAIL_FROM, APP_PASSWORD)
            
            success_count += 1
            print(f"  ✅ FRAUD email sent to {row.customer_email} for transaction {row.transaction_id} (Risk: {row.risk_level})")
            
        except Exception as e:
            failure_count += 1
            print(f"  ❌ Error processing fraud alert {row.alert_id}: {e}")
    
    print(f"📊 Batch {batch_id} complete: {success_count} succeeded, {failure_count} failed")


@dp.append_flow(target="fraud_email_notifier_sink")
def fraud_card_alert_stream():
    """Streaming flow that reads fraud card alerts."""
    return spark.readStream.table("finguard.gold.fraud_card_alert")