package com.fanbook.auth.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class BootstrapAdminInitializerTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:bootstrap_admin;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/bootstrap-admin-storage");
        registry.add("fanbook.bootstrap-admin.username", () -> "first-admin");
        registry.add("fanbook.bootstrap-admin.password", () -> "bootstrap-secret");
        registry.add("fanbook.bootstrap-admin.email", () -> "first-admin@example.test");
    }

    @Autowired
    UserRepository userRepository;

    @Autowired
    PasswordEncoder passwordEncoder;

    @Test
    void bootstrapsFirstAdminFromEnvironmentProperties() {
        UserEntity admin = userRepository.findByUsername("first-admin").orElseThrow();

        assertThat(admin.getEmail()).isEqualTo("first-admin@example.test");
        assertThat(admin.getRoles()).containsExactly(UserRole.ADMIN);
        assertThat(passwordEncoder.matches("bootstrap-secret", admin.getPasswordHash())).isTrue();
    }

    @Test
    void doesNotCreateAnotherBootstrapAdminWhenAdminAlreadyExists() throws Exception {
        BootstrapAdminInitializer initializer = new BootstrapAdminInitializer(
                new BootstrapAdminProperties("another-admin", "another-secret", null),
                passwordEncoder,
                userRepository
        );

        initializer.run(null);

        assertThat(userRepository.findByUsername("another-admin")).isEmpty();
        assertThat(userRepository.findAll()).hasSize(1);
    }
}
