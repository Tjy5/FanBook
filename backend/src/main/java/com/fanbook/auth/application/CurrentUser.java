package com.fanbook.auth.application;

import com.fanbook.auth.domain.UserRole;
import java.util.Set;

public record CurrentUser(Long id, String username, String email, Set<UserRole> roles) {

    public boolean hasRole(UserRole role) {
        return roles.contains(role);
    }
}
