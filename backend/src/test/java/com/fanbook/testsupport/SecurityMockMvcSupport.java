package com.fanbook.testsupport;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;

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

    public static RequestPostProcessor csrfToken() {
        return csrf();
    }
}
