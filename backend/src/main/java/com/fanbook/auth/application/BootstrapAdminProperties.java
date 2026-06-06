package com.fanbook.auth.application;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fanbook.bootstrap-admin")
public record BootstrapAdminProperties(String username, String password, String email) {
}
