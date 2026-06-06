package com.fanbook.auth.application;

import com.fanbook.auth.api.AdminUserListResponse;
import com.fanbook.auth.api.AdminUserResponse;
import com.fanbook.auth.api.CreateUserRequest;
import com.fanbook.auth.api.UpdateUserRolesRequest;
import com.fanbook.auth.domain.UserEntity;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.auth.infrastructure.UserRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Service
public class UserAdminService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public UserAdminService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional(readOnly = true)
    public AdminUserListResponse listUsers() {
        return new AdminUserListResponse(userRepository.findAll().stream()
                .sorted(Comparator.comparing(UserEntity::getUsername))
                .map(this::toResponse)
                .toList());
    }

    @Transactional
    public AdminUserResponse createUser(CreateUserRequest request) {
        String username = normalizeRequired(request == null ? null : request.username(), "username");
        String password = required(request == null ? null : request.password(), "password");
        String email = normalizeOptional(request == null ? null : request.email());
        Set<UserRole> roles = rolesOrDefault(request == null ? null : request.roles(), UserRole.MEMBER);
        if (userRepository.existsByUsername(username)) {
            throw new FanbookException(ErrorCode.USER_ALREADY_EXISTS, HttpStatus.CONFLICT, "User '" + username + "' already exists.");
        }
        if (email != null && userRepository.existsByEmail(email)) {
            throw new FanbookException(ErrorCode.USER_ALREADY_EXISTS, HttpStatus.CONFLICT, "Email is already assigned to another user.");
        }
        return toResponse(userRepository.save(new UserEntity(username, email, passwordEncoder.encode(password), roles)));
    }

    @Transactional
    public AdminUserResponse updateRoles(Long userId, UpdateUserRolesRequest request) {
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new FanbookException(ErrorCode.USER_NOT_FOUND, HttpStatus.NOT_FOUND, "User '" + userId + "' was not found."));
        Set<UserRole> roles = parseRoles(request == null ? null : request.roles());
        ensureAdminRemains(user, roles);
        user.replaceRoles(roles);
        return toResponse(user);
    }

    private void ensureAdminRemains(UserEntity user, Set<UserRole> nextRoles) {
        if (user.getRoles().contains(UserRole.ADMIN)
                && !nextRoles.contains(UserRole.ADMIN)
                && userRepository.countByRole(UserRole.ADMIN) <= 1) {
            throw new FanbookException(
                    ErrorCode.LAST_ADMIN_REQUIRED,
                    HttpStatus.CONFLICT,
                    "At least one admin user must remain."
            );
        }
    }

    private AdminUserResponse toResponse(UserEntity user) {
        return new AdminUserResponse(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.isEnabled(),
                user.getRoles().stream().map(Enum::name).sorted().toList(),
                user.getCreatedAt(),
                user.getUpdatedAt()
        );
    }

    private Set<UserRole> rolesOrDefault(List<String> values, UserRole fallback) {
        if (values == null || values.isEmpty()) {
            return EnumSet.of(fallback);
        }
        return parseRoles(values);
    }

    private Set<UserRole> parseRoles(List<String> values) {
        if (values == null || values.isEmpty()) {
            throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.BAD_REQUEST, "At least one role is required.");
        }
        EnumSet<UserRole> roles = EnumSet.noneOf(UserRole.class);
        for (String value : values) {
            try {
                roles.add(UserRole.valueOf(required(value, "role").toUpperCase(Locale.ROOT)));
            } catch (IllegalArgumentException exception) {
                throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.BAD_REQUEST, "Role '" + value + "' is not supported.");
            }
        }
        return roles;
    }

    private String normalizeRequired(String value, String field) {
        return required(value, field).trim();
    }

    private String normalizeOptional(String value) {
        return StringUtils.hasText(value) ? value.trim() : null;
    }

    private String required(String value, String field) {
        if (!StringUtils.hasText(value)) {
            throw new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.BAD_REQUEST, field + " is required.");
        }
        return value;
    }
}
