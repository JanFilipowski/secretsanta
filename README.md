# Secret Santa Automation

Generate Secret Santa assignments with hard constraints and deliver the results via email. The repository contains two small Python CLI programs:

- `transversal.py` – builds a perfect matching between gift givers and receivers using the Hopcroft–Karp algorithm while honouring per-person allowlists.
- `send.py` – validates the draw, renders templated emails, and sends individual notifications through SMTP.

The code uses only the Python standard library and runs anywhere Python 3.9+ is available.

## Repository layout
- `people.json` – participant list (`first_name`, `last_name`, `email`, optional `allowed`).
- `transversal.py` – draws constrained assignments and writes them to `results.json`.
- `results.json` – sample output produced by the draw step.
- `config.json` – SMTP host credentials plus an email template.
- `send.py` – email sender; supports dry runs and per-person lookups.

## Prerequisites
- Python 3.9 or newer.
- Access to an SMTP server that allows authenticated sending from the configured address.
- Optional: environment variable for the SMTP password (recommended instead of storing a password in `config.json`).

## 1. Prepare the participant list
Edit `people.json` and add one object per person:

```json
{
	"first_name": "Alicja",
	"last_name": "Boruta",
	"email": "aboruta@example.com",
	"allowed": ["Krzysztof Majerski", "Magdalena Serafin"]
}
```

- `full_name` is derived automatically as `first_name + last_name`.
- `allowed` lists everyone a person is permitted to draw. If omitted or empty, the person may draw anyone except themselves.
- Keep names unique; the scripts raise a clear error when duplicates or unknown references appear.

## 2. Generate assignments
`transversal.py` shuffles the graph multiple times and searches for a perfect matching.

```
python transversal.py --people people.json --results results.json
```

Useful knobs (see the top of `transversal.py`):
- `NUM_REPETITIONS` – how many shuffles to attempt (default 50).
- `RANDOM_SEED` – fix to an integer for repeatable draws.
- `STOP_ON_FIRST` – set to `False` to collect multiple valid matchings and choose one at random.

The script never prints the result; it writes a JSON blob shaped as `{"assignments": {"Giver": "Receiver"}}` to the path provided with `--results` (defaults to `results.json`).

## 3. Configure email delivery
`config.json` supplies SMTP details and the message template:

- `smtp.host`, `smtp.port`, `smtp.use_tls`, `smtp.username` – handed directly to `smtplib.SMTP`.
- `smtp.password` – optional; prefer `smtp.password_env_var` to pull the password from an environment variable.
- `email.from_email`, `email.subject`, `email.body` – the rendered email. The body supports placeholders such as `{giver_first}`, `{giver_full}`, `{target_full}`, `{target_email}`.

Tip: store `smtp.password` as `null` and export the password only for the sending session:

```
$env:SANTA_PASS = "super-secret"
python send.py --config config.json
```

Then add `"password_env_var": "SANTA_PASS"` inside the SMTP section.

## 4. Send notifications
Once `results.json` is ready, deliver the messages:

```
python send.py --people people.json --config config.json --results results.json
```

Flags:
- `--dry-run` – print every email instead of sending, ideal for verification.
- `--only "Full Name"` or `--only someone@example.com` – send (or preview) the message for a single participant.

`send.py` verifies that every giver and receiver from `results.json` exists in the current `people.json` before opening the SMTP connection.

## Troubleshooting
- **No perfect matching found** – relax the `allowed` lists or increase `NUM_REPETITIONS`. With overly strict constraints, a perfect matching might not exist.
- **SMTP authentication errors** – confirm TLS requirements, username, and passwords match your provider. Use the `--dry-run` flag to debug message formatting without touching SMTP.
- **Diacritics in emails** – the scripts open files as UTF-8 and send UTF-8 content. Ensure your terminal also uses UTF-8 if you need non-ASCII text.

## Extending the project
- Add extra metadata to `people.json` (for example, office location) and update the email template placeholders in `render_body`.
- Swap the output of `transversal.py` for another consumer (Slack, Teams, etc.) by replacing `save_results` with an API call.
- Implement automated scheduling by wrapping both scripts in a CI job once credentials can be injected securely.
