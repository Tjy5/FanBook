package com.fanbook.auth.application;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Component
@EnableConfigurationProperties(BootstrapAdminProperties.class)
public class BootstrapAdminInitializer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(BootstrapAdminInitializer.class);

    private final BootstrapAdminProperties properties;
    private final PasswordEncoder passwordEncoder;
    private final UserRepository userRepository;

    public BootstrapAdminInitializer(
            BootstrapAdminProperties properties,
            PasswordEncoder passwordEncoder,
            UserRepository userRepository
    ) {
        this.properties = properties;
        this.passwordEncoder = passwordEncoder;
        this.userRepository = userRepository;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (userRepository.existsByRole(UserRole.ADMIN)) {
            return;
        }
        if (!StringUtils.hasText(properties.username()) || !StringUtils.hasText(properties.password())) {
            log.warn("No admin user exists and bootstrap admin environment variables are not fully configured.");
            return;
        }
        String username = properties.username().trim();
        if (userRepository.existsByUsername(username)) {
            log.warn("Bootstrap admin username '{}' already exists without admin role; no bootstrap account was created.", username);
            return;
        }
        String email = StringUtils.hasText(properties.email()) ? properties.email().trim() : null;
        userRepository.save(new UserEntity(
                username,
                email,
                passwordEncoder.encode(properties.password()),
                Set.of(UserRole.ADMIN)
        ));
        log.info("Bootstrap admin user '{}' was created.", username);
    }
}
