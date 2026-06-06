package com.fanbook.auth.application;

public interface CurrentUserProvider {

    CurrentUser requireCurrentUser();
}
