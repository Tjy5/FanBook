package com.fanbook.auth.api;

import static com.fanbook.testsupport.SecurityMockMvcSupport.admin;
import static com.fanbook.testsupport.SecurityMockMvcSupport.csrfToken;
import static com.fanbook.testsupport.SecurityMockMvcSupport.member;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class UserAdminControllerIntegrationTest {

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:h2:mem:user_admin_controller;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1");
        registry.add("spring.datasource.driver-class-name", () -> "org.h2.Driver");
        registry.add("spring.jpa.database-platform", () -> "org.hibernate.dialect.H2Dialect");
        registry.add("fanbook.storage.root", () -> "target/user-admin-controller-storage");
    }

    @Autowired
    MockMvc mockMvc;

    @Autowired
    PasswordEncoder passwordEncoder;

    @Autowired
    UserRepository userRepository;

    private final ObjectMapper objectMapper = JsonMapper.builder().build();

    @BeforeEach
    void cleanUsers() {
        userRepository.deleteAll();
        userRepository.save(new UserEntity("admin", null, passwordEncoder.encode("secret"), Set.of(UserRole.ADMIN)));
    }

    @Test
    void adminCreatesListsAndUpdatesUserRoles() throws Exception {
        String created = mockMvc.perform(post("/api/admin/users")
                        .with(admin())
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"username\":\"alice\",\"password\":\"password-1\",\"email\":\"alice@example.test\",\"roles\":[\"member\"]}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.username").value("alice"))
                .andExpect(jsonPath("$.roles[0]").value("MEMBER"))
                .andReturn().getResponse().getContentAsString();
        Long userId = objectMapper.readTree(created).get("id").asLong();

        mockMvc.perform(get("/api/admin/users").with(admin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.users[0].username").value("admin"))
                .andExpect(jsonPath("$.users[1].username").value("alice"));

        mockMvc.perform(patch("/api/admin/users/" + userId + "/roles")
                        .with(admin())
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"roles\":[\"viewer\"]}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.roles[0]").value("VIEWER"));

        UserEntity updated = userRepository.findByUsername("alice").orElseThrow();
        assertThat(updated.getRoles()).containsExactly(UserRole.VIEWER);
        assertThat(passwordEncoder.matches("password-1", updated.getPasswordHash())).isTrue();
    }

    @Test
    void rejectsRemovingLastAdminRole() throws Exception {
        Long adminId = userRepository.findByUsername("admin").orElseThrow().getId();

        mockMvc.perform(patch("/api/admin/users/" + adminId + "/roles")
                        .with(admin())
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"roles\":[\"member\"]}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("last_admin_required"));

        assertThat(userRepository.findByUsername("admin").orElseThrow().getRoles())
                .containsExactly(UserRole.ADMIN);
    }

    @Test
    void memberCannotManageUsers() throws Exception {
        mockMvc.perform(get("/api/admin/users").with(member()))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/admin/users")
                        .with(member())
                        .with(csrfToken())
                        .contentType("application/json")
                        .content("{\"username\":\"bob\",\"password\":\"password-1\"}"))
                .andExpect(status().isForbidden());
    }

    @Test
    void adminUserMutationRequiresCsrf() throws Exception {
        mockMvc.perform(post("/api/admin/users")
                        .with(admin())
                        .contentType("application/json")
                        .content("{\"username\":\"bob\",\"password\":\"password-1\"}"))
                .andExpect(status().isForbidden());
    }
}
