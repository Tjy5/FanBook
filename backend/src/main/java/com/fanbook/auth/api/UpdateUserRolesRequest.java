package com.fanbook.auth.api;

import java.util.List;

public record UpdateUserRolesRequest(List<String> roles) {
}
