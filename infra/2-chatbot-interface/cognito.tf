# Cognito User Pool for Authentication
resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"
  
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
  
  tags = local.tags
}

resource "aws_cognito_user_pool_client" "client" {
  name                = "${local.name_prefix}-client"
  user_pool_id        = aws_cognito_user_pool.main.id
  generate_secret     = true
  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.name_prefix}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}