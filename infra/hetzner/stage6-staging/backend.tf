# Apply must supply the reviewed S3-compatible backend settings. State must
# never be written to this repository or a workflow runner's local disk.
terraform {
  backend "s3" {
    key                         = "codestra/stage6/staging-host.tfstate"
    use_lockfile                = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
  }
}
