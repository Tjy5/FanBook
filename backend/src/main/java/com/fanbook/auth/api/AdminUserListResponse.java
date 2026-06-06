package com.fanbook.auth.api;

import java.util.List;

public record AdminUserListResponse(List<AdminUserResponse> users) {
}
