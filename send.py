#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import os
import smtplib
from email.message import EmailMessage


# ============================
# Loading data
# ============================

def load_people(path):
    with open(path, "r", encoding="utf-8") as f:
        people = json.load(f)

    for p in people:
        p["full_name"] = f'{p["first_name"]} {p["last_name"]}'
    return people


def validate_people(people):
    names = [p["full_name"] for p in people]
    if len(names) != len(set(names)):
        raise ValueError("people.json contains duplicate full names (full_name).")

    people_by_name = {p["full_name"]: p for p in people}

    for p in people:
        full_name = p["full_name"]
        for target in p.get("allowed", []):
            if target not in people_by_name:
                raise ValueError(
                    f'Person "{full_name}" lists a non-existing allowed recipient: "{target}".'
                )
            if target == full_name:
                raise ValueError(
                    f'Person "{full_name}" lists themselves in allowed, which is unsupported.'
                )

    return people_by_name


def load_results(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "assignments" not in data:
        raise ValueError("Invalid results.json format – missing 'assignments' key.")

    assignments = data["assignments"]
    if not isinstance(assignments, dict):
        raise ValueError("The 'assignments' value in results.json must be a dictionary.")

    return assignments


def validate_results_against_people(assignments, people_by_name):
    for giver_name, target_name in assignments.items():
        if giver_name not in people_by_name:
            raise ValueError(
                f"Giver '{giver_name}' from results.json is missing in the current people.json."
            )
        if target_name not in people_by_name:
            raise ValueError(
                f"Recipient '{target_name}' (assigned to '{giver_name}') is missing in the current people.json."
            )


def select_assignments(assignments, people_by_name, only_identifier=None):
    """
    Returns either the full assignments dict or a single entry for a selected person.
    only_identifier:
      - full_name (e.g., "Jan Kowalski") OR
      - email (e.g., "jan.kowalski@example.com")
    """
    if not only_identifier:
        return assignments

    giver_name = None

    # 1) Try matching full_name
    if only_identifier in assignments:
        giver_name = only_identifier
    else:
        # 2) Try matching email address
        for full_name, person in people_by_name.items():
            if person.get("email") == only_identifier:
                giver_name = full_name
                break

    if giver_name is None:
        raise ValueError(
            f"No person found with full_name or email equal to '{only_identifier}'."
        )

    if giver_name not in assignments:
        raise ValueError(
            f"Person '{giver_name}' does not appear as a giver in results.json."
        )

    return {giver_name: assignments[giver_name]}


# ============================
# Sending emails
# ============================

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_body(template, giver, target):
    return template.format(
        giver_first=giver["first_name"],
        giver_last=giver["last_name"],
        giver_full=giver["full_name"],
        target_first=target["first_name"],
        target_last=target["last_name"],
        target_full=target["full_name"],
        target_email=target["email"],
    )


def send_emails(assignments, people_by_name, config, dry_run=False):
    """
    assignments: dict giver_full_name -> receiver_full_name
    people_by_name: dict full_name -> person_dict
    config: loaded config.json
    dry_run: when True, preview instead of sending
    """
    smtp_cfg = config["smtp"]
    email_cfg = config["email"]

    from_email = email_cfg["from_email"]
    subject = email_cfg["subject"]
    body_template = email_cfg["body"]

    # Password: prefer environment variable over inline password
    password = None
    env_var = smtp_cfg.get("password_env_var")
    if env_var:
        password = os.environ.get(env_var)
    if not password:
        password = smtp_cfg.get("password")

    if not dry_run and not password:
        raise ValueError(
            "Missing SMTP password: set the environment variable referenced in config.json "
            "or fall back to the less secure inline 'password' field."
        )

    if dry_run:
        print("=== DRY RUN – nothing will be sent, preview only ===")

    server = None
    if not dry_run:
        server = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"])
        if smtp_cfg.get("use_tls", True):
            server.starttls()
        if smtp_cfg.get("username"):
            server.login(smtp_cfg["username"], password)

    try:
        for giver_name, target_name in assignments.items():
            giver = people_by_name[giver_name]
            target = people_by_name[target_name]

            to_email = giver["email"]
            body = render_body(body_template, giver, target)

            msg = EmailMessage()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(body, subtype="plain", charset="utf-8")

            if dry_run:
                print("\n-----------------------------")
                print(f"TO: {to_email}")
                print(f"SUBJECT: {subject}")
                print("BODY:")
                print(body)
            else:
                server.send_message(msg)

    finally:
        if server is not None:
            server.quit()


# ============================
# CLI
# ============================

def main():
    parser = argparse.ArgumentParser(
        description="Send Secret Santa emails based on results.json."
    )
    parser.add_argument(
        "--people",
        default="people.json",
        help="Path to people.json (default: people.json).",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json).",
    )
    parser.add_argument(
        "--results",
        default="results.json",
        help="Path to results.json generated by transversal.py (default: results.json).",
    )
    parser.add_argument(
        "--only",
        help="Send only to a single person (provide full_name or email).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send emails, just print what would be sent.",
    )

    args = parser.parse_args()

    try:
        people = load_people(args.people)
        people_by_name = validate_people(people)

        assignments = load_results(args.results)
        validate_results_against_people(assignments, people_by_name)

        # Optional restriction to a single recipient
        assignments_to_send = select_assignments(
            assignments, people_by_name, args.only
        )

        config = load_config(args.config)

        send_emails(assignments_to_send, people_by_name, config, dry_run=args.dry_run)

        if args.dry_run:
            print("\nDry run finished – nothing was sent.")
        else:
            print("\nEmails sent! 🎅")

    except Exception as e:
        print(f"Error while sending emails: {e}")


if __name__ == "__main__":
    main()
