-module(auth_jwt_utils).

-export([generate_token/1, generate_token/2, validate_token/1]).

% Including jose.hrl as it seems to be the main include file for this version
-include_lib("jose/include/jose.hrl").
% -include_lib("jose/include/jose_jws.hrl"). % May not be needed if jose.hrl covers it or if atoms are used
-include_lib("jose/include/jose_jwt.hrl"). % For JWT specific record/claims, if used by jose_jwt:claims/1

%% @doc Generates a JWT token with default expiry (e.g., 1 hour).
generate_token(Payload) ->
    generate_token(Payload, 3600).

%% @doc Generates a JWT token with custom expiry.
generate_token(Payload, ExpirySeconds) ->
    Now = erlang:system_time(second),
    ClaimsMap = Payload#{
        iss => <<"crm_backend_auth_service">>,
        sub => maps:get(user_id, Payload, <<"unknown_user">>),
        aud => <<"crm_users">>,
        exp => Now + ExpirySeconds,
        nbf => Now - 60, % Not Before Time (allow 1 min clock skew)
        iat => Now, % Issued At
        jti => jose_lib:secure_random(16) % JWT ID
    },
    % IMPORTANT: Hardcoded secret key for demonstration ONLY.
    % This MUST be securely configured in a real system.
    SecretKey = crypto:strong_rand_bytes(32), % Using a generated key

    % Using the atom 'HS256' for the algorithm
    JWSHeader = #{alg => 'HS256'},

    try
        SignedJWT = jose_jwt:sign(SecretKey, JWSHeader, ClaimsMap),
        {ok, jose_jws:compact(SignedJWT)}
    catch
        Type:Reason:StackTrace ->
            error_logger:error_msg("Error generating JWT: ~p:~p~n~p~n", [Type, Reason, StackTrace]),
            {error, {jwt_generation_failed, Reason}}
    end.

%% @doc Validates a JWT token.
validate_token(Token) ->
    % IMPORTANT: Hardcoded secret key for demonstration ONLY.
    SecretKey = crypto:strong_rand_bytes(32), % Must be the same key used for signing

    ExpectedClaims = #{
        % iss => <<"crm_backend_auth_service">> % Example: if you want to enforce issuer
    },
    % Using the atom 'HS256' for the algorithm verification
    ValidationOpts = #{
        allowed_algs => ['HS256'], % Specify allowed algorithm(s) as a list of atoms
        claims => ExpectedClaims
        % max_age => 3600 * 24, % Example: 1 day, in seconds
        % clock_skew_intolerance => 60 % Example: 60 seconds
    },
    try
        case jose_jws:verify(SecretKey, ValidationOpts, Token) of
            {true, JWT, _Signature} ->
                % JWT verified, claims can be extracted
                {ok, jose_jwt:claims(JWT)}; % Returns the claims map
            {false, _JWT, Reason} ->
                 error_logger:error_msg("JWT validation failed: ~p~n", [Reason]),
                {error, Reason} % Reason could be 'invalid_signature', 'expired_token', etc.
        end
    catch
        Type:CatchReason:StackTrace ->
            error_logger:error_msg("Error validating JWT: ~p:~p~n~p~n", [Type, CatchReason, StackTrace]),
            {error, {jwt_validation_failed, CatchReason}}
    end.
