-module(auth_user_handler).
-behaviour(gen_server).

-export([start_link/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

% API
-export([login/4, get_dummy_user_hashed_password/0]). % login/2 changed to login/4

% Dummy User Data (replace with DB lookup later)
-define(DUMMY_USER_ID, <<"user_001">>).
-define(DUMMY_EMAIL, <<"test@example.com">>).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

init([]) ->
    {ok, HashedPassword} = auth_bcrypt_utils:hash_password(<<"password123">>),
    State = #{
        dummy_user => #{
            id => ?DUMMY_USER_ID,
            email => ?DUMMY_EMAIL,
            password_hash => HashedPassword
        }
    },
    io:format("~p: Dummy user initialized with hashed password.~n", [?MODULE]),
    {ok, State}.

handle_call({get_dummy_hash}, _From, State) ->
    HashedPassword = maps:get(password_hash, maps:get(dummy_user, State)),
    {reply, {ok, HashedPassword}, State};
handle_call(_Request, _From, State) ->
    {reply, {error, not_implemented}, State}.

handle_cast(_Msg, State) -> {noreply, State}.
handle_info(_Info, State) -> {noreply, State}.
terminate(_Reason, _State) -> ok.
code_change(_OldVsn, State, _Extra) -> {ok, State}.

%% ===================================================================
%% Public API Functions
%% ===================================================================

%% @doc Attempts to log in a user and audits the attempt.
%% @param Email :: binary() | string()
%% @param Password :: binary() | string()
%% @param IpAddress :: binary() | string() (Placeholder for now)
%% @param UserAgent :: binary() | string() (Placeholder for now)
%% @returns {ok, JwtToken :: binary()} | {error, Reason :: atom()}
login(Email, Password, IpAddress, UserAgent) ->
    CleanEmail = to_binary(Email), % Ensure Email is binary for consistent logging/comparison
    case gen_server:call(?MODULE, get_dummy_hash) of
        {ok, StoredHash} ->
            DummyUserId = ?DUMMY_USER_ID,
            DummyEmail = ?DUMMY_EMAIL,

            if CleanEmail =:= DummyEmail ->
                case auth_bcrypt_utils:check_password(Password, StoredHash) of
                    true ->
                        auth_audit_logger:log_login_success(DummyUserId, IpAddress, UserAgent),
                        Payload = #{user_id => DummyUserId, email => CleanEmail},
                        auth_jwt_utils:generate_token(Payload);
                    false ->
                        auth_audit_logger:log_login_failure(CleanEmail, IpAddress, UserAgent, invalid_password),
                        {error, invalid_credentials}
                end;
            true -> % Email does not match
                auth_audit_logger:log_login_failure(CleanEmail, IpAddress, UserAgent, email_not_found),
                {error, invalid_credentials}
            end;
        {error, Reason} ->
            error_logger:error_msg("~p: Could not fetch dummy hash for login: ~p~n", [?MODULE, Reason]),
            auth_audit_logger:log_login_failure(CleanEmail, IpAddress, UserAgent, internal_error_getting_hash),
            {error, internal_error}
    end.

get_dummy_user_hashed_password() ->
    gen_server:call(?MODULE, get_dummy_hash).

%% Internal utility
to_binary(X) when is_list(X) -> list_to_binary(X);
to_binary(X) when is_binary(X) -> X.
