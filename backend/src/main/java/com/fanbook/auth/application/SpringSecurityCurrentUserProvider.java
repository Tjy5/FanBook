package com.fanbook.auth.application;

import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.auth.domain.UserRole;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

@Component
public class SpringSecurityCurrentUserProvider implements CurrentUserProvider {

    @Override
    public CurrentUser requireCurrentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new FanbookException(ErrorCode.UNAUTHENTICATED, HttpStatus.UNAUTHORIZED, "Authentication is required.");
        }
        if (authentication.getPrincipal() instanceof LocalUserPrincipal principal) {
            return principal.toCurrentUser();
        }
        Set<UserRole> roles = authentication.getAuthorities().stream()
                .map(authority -> authority.getAuthority().replaceFirst("^ROLE_", ""))
                .filter(candidate -> Arrays.stream(UserRole.values()).anyMatch(role -> role.name().equals(candidate)))
                .map(UserRole::valueOf)
                .collect(Collectors.toUnmodifiableSet());
        return new CurrentUser(null, authentication.getName(), null, roles);
    }
}
