# Security and credentials

Keep your Predictefy API key in a local `.env` file or process environment. Never commit `.env`, upload it in an issue, or include it in a screenshot. The repository contains only `.env.example` with a placeholder.

The scripts run on your own computer and are read-only. They send the key in the `Authorization` header to `https://data.predictefy.com` and nowhere else, and they never print it. Recordings made with `PREDICTEFY_RECORD` store response bodies and the credits charged; they do not store request headers.

The scripts do not need a Polymarket private key, a Kalshi login, a seed phrase, a funded wallet or order permission. Do not add these to the configuration.

If you expose an API key, revoke or regenerate it at [portal.predictefy.com/keys](https://portal.predictefy.com/keys). Removing it from the latest file alone does not remove it from Git history.

For a suspected vulnerability, use the repository's private vulnerability reporting option under **Security → Report a vulnerability**. Use synthetic values in reproductions and avoid publishing credentials. Ordinary bugs can be reported in public issues with redacted output.
