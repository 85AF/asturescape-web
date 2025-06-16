-module(auth_audit_logger).
-behaviour(gen_server).

-export([start_link/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

% API for logging
-export([log_login_success/3, log_login_failure/4]).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

init([]) ->
    {ok, #{}}. % No state needed for now, could hold log file handle or config

handle_call(_Request, _From, State) ->
    {reply, {error, not_implemented}, State}.

handle_cast({log, Message}, State) ->
    % In a real system, this could write to a file, a database, or a logging service.
    % For now, just use error_logger.
    error_logger:info_msg("AUDIT: ~s~n", [Message]),
    {noreply, State}.

handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

%% ===================================================================
%% Public API Functions for Logging
%% ===================================================================

log_login_success(UserId, IpAddress, UserAgent) ->
    LogMessage = io_lib:format("Login success for UserID: ~p, IP: ~s, User-Agent: ~s", [UserId, to_string(IpAddress), to_string(UserAgent)]),
    gen_server:cast(?MODULE, {log, LogMessage}).

log_login_failure(Email, IpAddress, UserAgent, Reason) ->
    LogMessage = io_lib:format("Login failure for Email: ~s, IP: ~s, User-Agent: ~s, Reason: ~p", [to_string(Email), to_string(IpAddress), to_string(UserAgent), Reason]),
    gen_server:cast(?MODULE, {log, LogMessage}).

%% Internal utility
to_string(X) when is_list(X) -> X;
to_string(X) when is_binary(X) -> binary_to_list(X);
to_string(X) -> io_lib:format("~p", [X]).
