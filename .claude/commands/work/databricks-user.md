Generate Terraform resource blocks for new Databricks users, service principals, or groups.

Ask the user what they need to create: a **user**, a **service principal**, a **group**, or any combination.

## Step 1: Check for existing user

Before generating any resource block, if a user (email) is being created, search `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf` for the provided email address.

- If the email is **already present** in the file, stop immediately and inform the user that the email already exists in `users.tf`. Do not generate any resource block.
- If the email is **not found**, proceed with generating the resource block.

## Step 2: Insert into users.tf

After generating a user resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf`. Add a blank line before the new block if the file does not already end with one.

---

## User

The user will provide: full name and email address.

Template:

```hcl
resource "databricks_user" "<short_name>" {
  provider     = databricks.accounts
  user_name    = "<email>"
  force        = true
  display_name = "<Full Name>"
}
```

Rules:
- `<short_name>` is derived from the email prefix (the part before `@`), with any dots removed. For example, `neel.oza@demonware.net` becomes `neeloza`, `jshao@demonware.net` becomes `jshao`.
- `<email>` is the full email address provided.
- `<Full Name>` is the display name provided by the user.

---

## Service Principal

The user will provide: a display name for the service principal.

Template:

```hcl
resource "databricks_service_principal" "<resource_name>" {
  provider     = databricks.accounts
  force        = true
  display_name = "<display_name>"
}
```

Rules:
- `<resource_name>` is the display name with hyphens replaced by underscores. For example, `dbx-sp-dw-client-code` becomes `dbx_sp_dw_client_code`.
- `<display_name>` is the display name exactly as provided by the user.
- Before generating, search `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf` for the display name. If it is already present, stop and inform the user. Do not generate any resource block.
- After generating the resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf`. Add a blank line before the new block if the file does not already end with one.

---

## Group

The user will provide: a display name for the group.

Template:

```hcl
resource "databricks_group" "<resource_name>" {
  provider     = databricks.accounts
  force        = true
  display_name = "<display_name>"
}
```

Rules:
- `<resource_name>` is the display name with hyphens replaced by underscores. For example, `dbx-grp-ap` becomes `dbx_grp_ap`.
- `<display_name>` is the display name exactly as provided by the user.

After generating the group resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/groups.tf`. Add a blank line before the new block if the file does not already end with one.

---

## Common Rules
- Always use `provider = databricks.accounts`.
- Always set `force = true`.
- Output only the resource block(s), no extra explanation.
- If the user provides multiple entries, generate one resource block per entry.
