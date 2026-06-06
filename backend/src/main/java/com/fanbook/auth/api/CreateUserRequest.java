package com.fanbook.auth.api;

import java.util.List;

public record CreateUserRequest(String username, String password, String email, List<String> roles) {
}
