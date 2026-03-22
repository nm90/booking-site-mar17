#!/usr/bin/env bash
set -euo pipefail

#───────────────────────────────────────────────────────────────────────
# Booking Site Mar17 — GitHub Project Setup
# 
# Converts the project plan into:
#   • A GitHub Projects V2 board (private) with custom fields
#   • 25 user-story issues + 4 bug issues, all linked to the project
#   • Labels for epics, priorities, phases, and type
#
# PREREQUISITES:
#   1. Install GitHub CLI: https://cli.github.com
#   2. Authenticate:  gh auth login
#   3. Make sure you have admin access to nm90/booking-site-mar17
#
# USAGE:
#   chmod +x setup_project.sh
#   ./setup_project.sh
#───────────────────────────────────────────────────────────────────────

OWNER="nm90"
REPO="booking-site-mar17"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  Booking Site Mar17 — GitHub Project Setup           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Verify gh is available and authenticated
if ! command -v gh &>/dev/null; then
  echo "❌ GitHub CLI (gh) not found. Install from https://cli.github.com"
  exit 1
fi
gh auth status || { echo "❌ Not authenticated. Run: gh auth login"; exit 1; }

#───────────────────────────────────────────────
# 1. Create labels
#───────────────────────────────────────────────
echo "🏷️  Creating labels..."
declare -A LABELS=(
  ["epic:security"]="D73A4A"
  ["epic:database"]="E4572E"
  ["epic:business-logic"]="F9C513"
  ["epic:user-mgmt"]="0E8A16"
  ["epic:admin"]="1D76DB"
  ["epic:customer-exp"]="7057FF"
  ["epic:payments"]="FF69B4"
  ["epic:devops"]="6A737D"
  ["priority:critical"]="B60205"
  ["priority:high"]="D93F0B"
  ["priority:medium"]="FBCA04"
  ["priority:low"]="0075CA"
  ["user-story"]="0E8A16"
  ["phase-1"]="B60205"
  ["phase-2"]="D93F0B"
  ["phase-3"]="0E8A16"
  ["phase-4"]="1D76DB"
)

for label in "${!LABELS[@]}"; do
  gh label create "$label" --color "${LABELS[$label]}" --repo "$OWNER/$REPO" --force 2>/dev/null && \
    echo "  ✓ $label" || echo "  ⊘ $label (exists)"
done

#───────────────────────────────────────────────
# 2. Create GitHub Project (V2)
#───────────────────────────────────────────────
echo ""
echo "📋 Creating GitHub Project..."

USER_ID=$(gh api graphql -f query='{ viewer { id } }' --jq '.data.viewer.id')

PROJECT_ID=$(gh api graphql -f query="
mutation {
  createProjectV2(input: {ownerId: \"$USER_ID\", title: \"Booking Site Mar17 — Project Plan\"}) {
    projectV2 { id number url }
  }
}" --jq '.data.createProjectV2.projectV2.id')

PROJECT_URL=$(gh api graphql -f query="
query {
  node(id: \"$PROJECT_ID\") { ... on ProjectV2 { url } }
}" --jq '.data.node.url')

echo "  ✓ Project created: $PROJECT_URL"

# Make private + add description
gh api graphql -f query="
mutation {
  updateProjectV2(input: {
    projectId: \"$PROJECT_ID\"
    public: false
    shortDescription: \"Actionable backlog from code review: 8 epics, 25 user stories, 4 bugs. 104 story points.\"
  }) { projectV2 { id } }
}" --silent

# Link repo
REPO_ID=$(gh api "repos/$OWNER/$REPO" --jq '.node_id')
gh api graphql -f query="
mutation {
  linkProjectV2ToRepository(input: {projectId: \"$PROJECT_ID\", repositoryId: \"$REPO_ID\"}) {
    repository { id }
  }
}" --silent
echo "  ✓ Linked to $OWNER/$REPO"

#───────────────────────────────────────────────
# 3. Create custom fields
#───────────────────────────────────────────────
echo ""
echo "⚙️  Adding custom fields..."

# Priority
PRIORITY_FIELD=$(gh api graphql -f query='
mutation {
  createProjectV2Field(input: {
    projectId: "'"$PROJECT_ID"'"
    dataType: SINGLE_SELECT
    name: "Priority"
    singleSelectOptions: [
      {name: "Critical", color: RED, description: "Deployment blocker"}
      {name: "High", color: ORANGE, description: "First sprint cycle"}
      {name: "Medium", color: YELLOW, description: "Next 2-3 sprints"}
      {name: "Low", color: BLUE, description: "As capacity allows"}
    ]
  }) { projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } } }
}' --jq '.data.createProjectV2Field.projectV2Field')
PRIORITY_ID=$(echo "$PRIORITY_FIELD" | jq -r '.id')
echo "  ✓ Priority field"

# Epic
EPIC_FIELD=$(gh api graphql -f query='
mutation {
  createProjectV2Field(input: {
    projectId: "'"$PROJECT_ID"'"
    dataType: SINGLE_SELECT
    name: "Epic"
    singleSelectOptions: [
      {name: "E-1: Security Hardening", color: RED, description: ""}
      {name: "E-2: Database & Data Integrity", color: ORANGE, description: ""}
      {name: "E-3: Business Logic & Data Model", color: YELLOW, description: ""}
      {name: "E-4: User Account Management", color: GREEN, description: ""}
      {name: "E-5: Admin Tooling", color: BLUE, description: ""}
      {name: "E-6: Customer Experience", color: PURPLE, description: ""}
      {name: "E-7: Notifications & Payments", color: PINK, description: ""}
      {name: "E-8: DevOps & Production Readiness", color: GRAY, description: ""}
    ]
  }) { projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } } }
}' --jq '.data.createProjectV2Field.projectV2Field')
EPIC_ID=$(echo "$EPIC_FIELD" | jq -r '.id')
echo "  ✓ Epic field"

# Story Points
SP_ID=$(gh api graphql -f query='
mutation {
  createProjectV2Field(input: {
    projectId: "'"$PROJECT_ID"'"
    dataType: NUMBER
    name: "Story Points"
  }) { projectV2Field { ... on ProjectV2Field { id } } }
}' --jq '.data.createProjectV2Field.projectV2Field.id')
echo "  ✓ Story Points field"

# Phase
PHASE_FIELD=$(gh api graphql -f query='
mutation {
  createProjectV2Field(input: {
    projectId: "'"$PROJECT_ID"'"
    dataType: SINGLE_SELECT
    name: "Phase"
    singleSelectOptions: [
      {name: "Phase 1: Security & Stability", color: RED, description: ""}
      {name: "Phase 2: Data & Core Logic", color: ORANGE, description: ""}
      {name: "Phase 3: User & Admin Features", color: GREEN, description: ""}
      {name: "Phase 4: Revenue & Comms", color: BLUE, description: ""}
    ]
  }) { projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } } }
}' --jq '.data.createProjectV2Field.projectV2Field')
PHASE_ID=$(echo "$PHASE_FIELD" | jq -r '.id')
echo "  ✓ Phase field"

# Get Status field
STATUS_FIELD=$(gh api graphql -f query='
query {
  node(id: "'"$PROJECT_ID"'") {
    ... on ProjectV2 {
      fields(first: 20) {
        nodes { ... on ProjectV2SingleSelectField { id name options { id name } } }
      }
    }
  }
}' --jq '.data.node.fields.nodes[] | select(.name == "Status")')
STATUS_ID=$(echo "$STATUS_FIELD" | jq -r '.id')

#───────────────────────────────────────────────
# Helper: option ID lookup
#───────────────────────────────────────────────
get_option_id() {
  local field_json="$1" name="$2"
  echo "$field_json" | jq -r --arg n "$name" '.options[] | select(.name == $n) | .id'
}

#───────────────────────────────────────────────
# Helper: create issue → add to project → set fields
#───────────────────────────────────────────────
create_item() {
  local title="$1" body="$2" labels="$3" priority="$4" epic="$5" phase="$6" points="$7"

  # Create issue
  local issue_url
  issue_url=$(gh issue create --repo "$OWNER/$REPO" \
    --title "$title" --body "$body" --label "$labels" 2>&1) || {
    echo "  ❌ Failed to create: $title"
    return
  }
  local issue_num="${issue_url##*/}"
  echo "  ✓ #$issue_num — $title"

  # Get node ID
  local node_id
  node_id=$(gh api "repos/$OWNER/$REPO/issues/$issue_num" --jq '.node_id')

  # Add to project
  local item_id
  item_id=$(gh api graphql -f query="
  mutation {
    addProjectV2ItemById(input: {projectId: \"$PROJECT_ID\", contentId: \"$node_id\"}) {
      item { id }
    }
  }" --jq '.data.addProjectV2ItemById.item.id')

  # Set Priority
  local popt
  popt=$(get_option_id "$PRIORITY_FIELD" "$priority")
  [ -n "$popt" ] && gh api graphql -f query="
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: \"$PROJECT_ID\", itemId: \"$item_id\",
      fieldId: \"$PRIORITY_ID\", value: {singleSelectOptionId: \"$popt\"}
    }) { projectV2Item { id } }
  }" --silent

  # Set Epic
  local eopt
  eopt=$(get_option_id "$EPIC_FIELD" "$epic")
  [ -n "$eopt" ] && gh api graphql -f query="
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: \"$PROJECT_ID\", itemId: \"$item_id\",
      fieldId: \"$EPIC_ID\", value: {singleSelectOptionId: \"$eopt\"}
    }) { projectV2Item { id } }
  }" --silent

  # Set Phase
  local phopt
  phopt=$(get_option_id "$PHASE_FIELD" "$phase")
  [ -n "$phopt" ] && gh api graphql -f query="
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: \"$PROJECT_ID\", itemId: \"$item_id\",
      fieldId: \"$PHASE_ID\", value: {singleSelectOptionId: \"$phopt\"}
    }) { projectV2Item { id } }
  }" --silent

  # Set Story Points
  if [ "$points" != "0" ] && [ -n "$points" ]; then
    gh api graphql -f query="
    mutation {
      updateProjectV2ItemFieldValue(input: {
        projectId: \"$PROJECT_ID\", itemId: \"$item_id\",
        fieldId: \"$SP_ID\", value: {number: $points}
      }) { projectV2Item { id } }
    }" --silent
  fi

  # Set Status → Todo
  local todo_id
  todo_id=$(get_option_id "$STATUS_FIELD" "Todo")
  [ -n "$todo_id" ] && gh api graphql -f query="
  mutation {
    updateProjectV2ItemFieldValue(input: {
      projectId: \"$PROJECT_ID\", itemId: \"$item_id\",
      fieldId: \"$STATUS_ID\", value: {singleSelectOptionId: \"$todo_id\"}
    }) { projectV2Item { id } }
  }" --silent

  sleep 0.3
}

#───────────────────────────────────────────────
# 4. Create all issues
#───────────────────────────────────────────────
echo ""
echo "📝 Creating user stories..."

# E-1: Security Hardening
create_item "[US-101] Implement bcrypt/argon2 password hashing" \
"**US-101 · Critical · 5 pts**

**Story:** Implement bcrypt/argon2 password hashing

**Acceptance Criteria:**
- All passwords hashed with bcrypt (cost ≥ 12) or argon2
- Existing SHA-256 hashes migrated on next login
- No two identical passwords produce the same hash" \
"user-story,epic:security,priority:critical,phase-1" "Critical" "E-1: Security Hardening" "Phase 1: Security & Stability" 5

create_item "[US-102] Enforce secure SECRET_KEY generation" \
"**US-102 · Critical · 3 pts**

**Story:** Enforce secure SECRET_KEY generation

**Acceptance Criteria:**
- App refuses to start if SECRET_KEY is the default dev value
- Dockerfile and docker-compose inject a cryptographically random key
- Documentation updated" \
"user-story,epic:security,priority:critical,phase-1" "Critical" "E-1: Security Hardening" "Phase 1: Security & Stability" 3

create_item "[US-103] Add CSRF protection to all POST forms" \
"**US-103 · Critical · 5 pts**

**Story:** Add CSRF protection to all POST forms

**Acceptance Criteria:**
- Flask-WTF integrated
- Every POST endpoint validates a CSRF token
- Requests without valid tokens return 403" \
"user-story,epic:security,priority:critical,phase-1" "Critical" "E-1: Security Hardening" "Phase 1: Security & Stability" 5

create_item "[US-104] Add server-side session validation" \
"**US-104 · High · 5 pts**

**Story:** Add server-side session validation

**Acceptance Criteria:**
- login_required and admin_required decorators re-verify user existence, active status, and role from the database on every request" \
"user-story,epic:security,priority:high,phase-1" "High" "E-1: Security Hardening" "Phase 1: Security & Stability" 5

create_item "[US-105] Implement booking status state machine" \
"**US-105 · High · 3 pts**

**Story:** Implement booking status state machine

**Acceptance Criteria:**
- Booking.update_status enforces valid transitions (e.g., pending→approved, pending→rejected, approved→cancelled)
- Invalid transitions raise ValueError" \
"user-story,epic:security,priority:high,phase-1" "High" "E-1: Security Hardening" "Phase 1: Security & Stability" 3

# E-2: Database & Data Integrity
create_item "[US-201] Implement connection pooling / reuse" \
"**US-201 · High · 5 pts**

**Story:** Implement connection pooling / reuse

**Acceptance Criteria:**
- Connections are pooled or reused per-request instead of opened/closed per query
- Benchmark shows ≥ 2x throughput improvement under load" \
"user-story,epic:database,priority:high,phase-2" "High" "E-2: Database & Data Integrity" "Phase 2: Data & Core Logic" 5

create_item "[US-202] Centralize DB_PATH configuration" \
"**US-202 · Medium · 2 pts**

**Story:** Centralize DB_PATH configuration

**Acceptance Criteria:**
- Single source of truth for DB_PATH used by connection.py, seed.py, and app.py
- No independent path resolution" \
"user-story,epic:database,priority:medium,phase-2" "Medium" "E-2: Database & Data Integrity" "Phase 2: Data & Core Logic" 2

create_item "[US-203] Make availability check + insert atomic" \
"**US-203 · High · 5 pts**

**Story:** Make availability check + insert atomic

**Acceptance Criteria:**
- check_availability and booking insert wrapped in a single transaction with appropriate locking
- Concurrent requests cannot create overlapping bookings" \
"user-story,epic:database,priority:high,phase-2" "High" "E-2: Database & Data Integrity" "Phase 2: Data & Core Logic" 5

# E-3: Business Logic & Data Model
create_item "[US-301] Build Property model and CRUD" \
"**US-301 · High · 8 pts**

**Story:** Build Property model and CRUD

**Acceptance Criteria:**
- Property model created
- Admin can create, edit, and delete properties via UI
- Booking.create references selected property instead of hardcoded property_id=1" \
"user-story,epic:business-logic,priority:high,phase-2" "High" "E-3: Business Logic & Data Model" "Phase 2: Data & Core Logic" 8

create_item "[US-302] Make pricing dynamic per property" \
"**US-302 · High · 5 pts**

**Story:** Make pricing dynamic per property

**Acceptance Criteria:**
- Price pulled from property record
- \$450 hardcoded value removed
- Booking total calculated from property nightly rate × nights" \
"user-story,epic:business-logic,priority:high,phase-2" "High" "E-3: Business Logic & Data Model" "Phase 2: Data & Core Logic" 5

create_item "[US-303] Add completed booking status and enforce review eligibility" \
"**US-303 · Medium · 3 pts**

**Story:** Add 'completed' booking status and enforce review eligibility

**Acceptance Criteria:**
- Bookings auto-transition to 'completed' after checkout date
- Reviews can only be left on completed bookings, not future stays" \
"user-story,epic:business-logic,priority:medium,phase-2" "Medium" "E-3: Business Logic & Data Model" "Phase 2: Data & Core Logic" 3

create_item "[US-304] Display calculated Nights value in bookings table" \
"**US-304 · Low · 1 pt**

**Story:** Display calculated Nights value in bookings table

**Acceptance Criteria:**
- Nights column shows calculated (checkout − checkin) instead of '---'" \
"user-story,epic:business-logic,priority:low,phase-2" "Low" "E-3: Business Logic & Data Model" "Phase 2: Data & Core Logic" 1

# E-4: User Account Management
create_item "[US-401] Build user profile editing (name, email)" \
"**US-401 · Medium · 5 pts**

**Story:** Build user profile editing (name, email)

**Acceptance Criteria:**
- Users can view and edit their profile
- Route, controller, and template created
- User.update() wired end-to-end" \
"user-story,epic:user-mgmt,priority:medium,phase-3" "Medium" "E-4: User Account Management" "Phase 3: User & Admin Features" 5

create_item "[US-402] Build password change flow" \
"**US-402 · Medium · 3 pts**

**Story:** Build password change flow

**Acceptance Criteria:**
- Users can change their password
- Old password required for verification
- New password hashed with bcrypt" \
"user-story,epic:user-mgmt,priority:medium,phase-3" "Medium" "E-4: User Account Management" "Phase 3: User & Admin Features" 3

create_item "[US-403] Build account deletion / deactivation" \
"**US-403 · Low · 3 pts**

**Story:** Build account deletion / deactivation

**Acceptance Criteria:**
- Users can request account deletion
- Associated bookings handled per business rules" \
"user-story,epic:user-mgmt,priority:low,phase-3" "Low" "E-4: User Account Management" "Phase 3: User & Admin Features" 3

# E-5: Admin Tooling
create_item "[US-501] Build admin adventure CRUD" \
"**US-501 · Medium · 5 pts**

**Story:** Build admin adventure CRUD

**Acceptance Criteria:**
- Admins can create, edit, and deactivate adventures from the admin UI
- No direct DB access required" \
"user-story,epic:admin,priority:medium,phase-3" "Medium" "E-5: Admin Tooling" "Phase 3: User & Admin Features" 5

create_item "[US-502] Add pagination to admin dashboard" \
"**US-502 · Medium · 3 pts**

**Story:** Add pagination to admin dashboard

**Acceptance Criteria:**
- Bookings, users, and adventures paginated (default 25/page)
- No full-table scans on dashboard load" \
"user-story,epic:admin,priority:medium,phase-3" "Medium" "E-5: Admin Tooling" "Phase 3: User & Admin Features" 3

# E-6: Customer Experience
create_item "[US-601] Add client-side form validation" \
"**US-601 · Medium · 3 pts**

**Story:** Add client-side form validation

**Acceptance Criteria:**
- Date inputs enforce min=today
- Guest count validated against property capacity
- Inline error messages displayed" \
"user-story,epic:customer-exp,priority:medium,phase-3" "Medium" "E-6: Customer Experience" "Phase 3: User & Admin Features" 3

create_item "[US-602] Sync frontend/backend guest limits" \
"**US-602 · Medium · 2 pts**

**Story:** Sync frontend/backend guest limits

**Acceptance Criteria:**
- HTML max attribute matches backend validation (property capacity)
- No discrepancy between max=8 and backend limit of 20" \
"user-story,epic:customer-exp,priority:medium,phase-3" "Medium" "E-6: Customer Experience" "Phase 3: User & Admin Features" 2

create_item "[US-603] Add search and filtering for customers" \
"**US-603 · Medium · 5 pts**

**Story:** Add search and filtering for customers

**Acceptance Criteria:**
- Customers can filter bookings by date range
- Adventures searchable by text
- Results paginated" \
"user-story,epic:customer-exp,priority:medium,phase-3" "Medium" "E-6: Customer Experience" "Phase 3: User & Admin Features" 5

# E-7: Notifications & Payments
create_item "[US-701] Integrate payment processing (Stripe)" \
"**US-701 · High · 13 pts**

**Story:** Integrate payment processing (Stripe)

**Acceptance Criteria:**
- Checkout flow captures payment via Stripe
- Bookings not approved without successful charge or deposit
- Refund flow for cancellations" \
"user-story,epic:payments,priority:high,phase-4" "High" "E-7: Notifications & Payments" "Phase 4: Revenue & Comms" 13

create_item "[US-702] Build transactional email system" \
"**US-702 · High · 8 pts**

**Story:** Build transactional email system

**Acceptance Criteria:**
- Confirmation email on booking creation
- Notification on approval/rejection
- Password reset email
- Configurable SMTP or third-party provider" \
"user-story,epic:payments,priority:high,phase-4" "High" "E-7: Notifications & Payments" "Phase 4: Revenue & Comms" 8

# E-8: DevOps & Production Readiness
create_item "[US-801] Replace Flask dev server with gunicorn/waitress" \
"**US-801 · High · 2 pts**

**Story:** Replace Flask dev server with gunicorn/waitress

**Acceptance Criteria:**
- Dockerfile and Procfile use gunicorn (or waitress on Windows)
- Flask built-in server not used in production" \
"user-story,epic:devops,priority:high,phase-1" "High" "E-8: DevOps & Production Readiness" "Phase 1: Security & Stability" 2

create_item "[US-802] Remove unused flask-cors dependency or integrate it" \
"**US-802 · Low · 1 pt**

**Story:** Remove unused flask-cors dependency or integrate it

**Acceptance Criteria:**
- flask-cors either imported and configured, or removed from requirements.txt" \
"user-story,epic:devops,priority:low,phase-1" "Low" "E-8: DevOps & Production Readiness" "Phase 1: Security & Stability" 1

create_item "[US-803] Set production log level to WARNING/ERROR" \
"**US-803 · Medium · 1 pt**

**Story:** Set production log level to WARNING/ERROR

**Acceptance Criteria:**
- File handler log level set to WARNING in production
- DEBUG reserved for development
- Log rotation configured" \
"user-story,epic:devops,priority:medium,phase-1" "Medium" "E-8: DevOps & Production Readiness" "Phase 1: Security & Stability" 1

# Bugs
echo ""
echo "🐛 Creating bugs..."

create_item "[BUG-001] get_by_id strips user_id when include_relations=True" \
"**BUG-001 · Severity: High**

**Description:** Booking.get_by_id with include_relations=True strips all keys starting with 'user_' including user_id, causing data loss in the returned dict.

**Suggested Fix:** Use an explicit exclusion list instead of prefix-based stripping, or rename the relation keys to avoid the collision." \
"bug,epic:database,priority:high,phase-1" "High" "E-2: Database & Data Integrity" "Phase 1: Security & Stability" 0

create_item "[BUG-002] Guest limit mismatch between frontend and backend" \
"**BUG-002 · Severity: Medium**

**Description:** Booking form HTML sets max=8 for guests but backend validation allows up to 20. Users who edit the DOM or POST directly can book 20 guests for a property with capacity 8.

**Suggested Fix:** Backend validation should use the property's actual capacity. Frontend max attribute should be dynamically set from property data." \
"bug,epic:customer-exp,priority:medium,phase-1" "Medium" "E-6: Customer Experience" "Phase 1: Security & Stability" 0

create_item "[BUG-003] Double-booking race condition on concurrent requests" \
"**BUG-003 · Severity: High**

**Description:** check_availability and booking insert are not atomic. Two concurrent requests can both pass the availability check and both insert, creating overlapping bookings.

**Suggested Fix:** Wrap availability check and insert in a single transaction with exclusive locking (BEGIN EXCLUSIVE in SQLite)." \
"bug,epic:database,priority:high,phase-1" "High" "E-2: Database & Data Integrity" "Phase 1: Security & Stability" 0

create_item "[BUG-004] Suspended user sessions remain valid" \
"**BUG-004 · Severity: High**

**Description:** Suspending a user does not invalidate their active session. login_required does not re-verify the user's status against the database, allowing suspended users to continue operating.

**Suggested Fix:** login_required decorator must query the database to verify user exists and is active on every request." \
"bug,epic:security,priority:high,phase-1" "High" "E-1: Security Hardening" "Phase 1: Security & Stability" 0

#───────────────────────────────────────────────
# Done!
#───────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete!                                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Project : $PROJECT_URL"
echo "║  Issues  : https://github.com/$OWNER/$REPO/issues"
echo "║  Items   : 25 user stories + 4 bugs                 ║"
echo "║  Points  : 104 total across 4 phases                ║"
echo "╚══════════════════════════════════════════════════════╝"
