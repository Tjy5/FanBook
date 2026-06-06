package com.fanbook.testsupport;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;

import com.fanbook.auth.application.LocalUserPrincipal;
import com.fanbook.auth.domain.UserRole;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

public final class SecurityMockMvcSupport {

    private SecurityMockMvcSupport() {
    }

    public static RequestPostProcessor admin() {
        return user("admin").roles("ADMIN");
    }

    public static RequestPostProcessor member() {
        return user("member").roles("MEMBER");
    }

    public static RequestPostProcessor viewer() {
        return user("viewer").roles("VIEWER");
    }

    public static RequestPostProcessor member(Long id, String username) {
        return localUser(id, username, UserRole.MEMBER);
    }

    public static RequestPostProcessor viewer(Long id, String username) {
        return localUser(id, username, UserRole.VIEWER);
    }

    public static RequestPostProcessor localUser(Long id, String username, UserRole... roles) {
        Set<UserRole> roleSet = Arrays.stream(roles).collect(Collectors.toUnmodifiableSet());
        return user(new LocalUserPrincipal(
                id,
                username,
                username + "@example.test",
                "{noop}password",
                true,
                roleSet
        ));
    }

    public static RequestPostProcessor csrfToken() {
        return csrf();
    }
}
