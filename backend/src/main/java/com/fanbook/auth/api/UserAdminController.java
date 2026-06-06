package com.fanbook.auth.api;

import com.fanbook.auth.application.UserAdminService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UserAdminController {

    private final UserAdminService userAdminService;

    public UserAdminController(UserAdminService userAdminService) {
        this.userAdminService = userAdminService;
    }

    @GetMapping("/api/admin/users")
    public AdminUserListResponse listUsers() {
        return userAdminService.listUsers();
    }

    @PostMapping("/api/admin/users")
    @ResponseStatus(HttpStatus.CREATED)
    public AdminUserResponse createUser(@RequestBody CreateUserRequest request) {
        return userAdminService.createUser(request);
    }

    @PatchMapping("/api/admin/users/{userId}/roles")
    public AdminUserResponse updateRoles(@PathVariable Long userId, @RequestBody UpdateUserRolesRequest request) {
        return userAdminService.updateRoles(userId, request);
    }
}
