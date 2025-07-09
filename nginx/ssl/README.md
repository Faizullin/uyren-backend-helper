# SSL Certificate Directory

This directory is for SSL certificates when deploying to production with HTTPS.

## Self-signed certificates for testing:

```bash
# Generate self-signed certificate for testing
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

## Production certificates:

For production, use certificates from:
- Let's Encrypt (free)
- Your domain provider
- Cloud provider (AWS Certificate Manager, etc.)

Place your certificate files here:
- `cert.pem` - SSL certificate
- `key.pem` - Private key

Make sure to update the nginx.conf file with the correct paths and uncomment the HTTPS server block.
