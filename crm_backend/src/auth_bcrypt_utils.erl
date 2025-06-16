-module(auth_bcrypt_utils).

-export([hash_password/1, check_password/2]).

%% @doc Hashes a password using fast_pbkdf2 (PBKDF2-SHA512).
%% @param Password :: string() | binary()
%% @returns {ok, binary()} | {error, any()}
hash_password(Password) ->
    Salt = crypto:strong_rand_bytes(16),
    Iterations = 200000, % Adjust as needed
    DerivedKeyLength = 32, % 256 bits
    try
        Hashed = fast_pbkdf2:pbkdf2(sha512, Password, Salt, Iterations, DerivedKeyLength),
        StoredHash = <<Salt/binary, Iterations:32/integer, DerivedKeyLength:16/integer, Hashed/binary>>,
        {ok, StoredHash}
    catch
        Type:Reason:StackTrace ->
            error_logger:error_msg("Error hashing password: ~p:~p~n~p~n", [Type, Reason, StackTrace]),
            {error, {hashing_failed, Reason}}
    end.

%% @doc Checks a password against a fast_pbkdf2 hash.
%% @param Password :: string() | binary()
%% @param StoredHashPackage :: binary()
%% @returns boolean()
check_password(Password, StoredHashPackage) ->
    try
        <<Salt:16/binary, Iterations:32/integer, DerivedKeyLength:16/integer, StoredHashedKey/binary>> = StoredHashPackage,
        CalculatedHashed = fast_pbkdf2:pbkdf2(sha512, Password, Salt, Iterations, DerivedKeyLength),
        CalculatedHashed == StoredHashedKey
    catch
        Type:Reason:StackTrace ->
            error_logger:error_msg("Error checking password: ~p:~p~n~p~n", [Type, Reason, StackTrace]),
            false
    end.
