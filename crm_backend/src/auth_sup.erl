-module(auth_sup).
-behaviour(supervisor).

-export([start_link/0]).
-export([init/1]).

start_link() ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, []).

init([]) ->
    SupFlags = #{strategy => one_for_one, intensity => 3, period => 10}, % Adjusted intensity and period
    ChildSpecs = [
        #{
            id => auth_user_handler_service,
            start => {auth_user_handler, start_link, []},
            restart => permanent,
            shutdown => 2000,
            type => worker, % It's a gen_server
            modules => [auth_user_handler]
        },
        #{
            id => auth_audit_logger_service,
            start => {auth_audit_logger, start_link, []},
            restart => permanent,
            shutdown => 2000,
            type => worker, % It's a gen_server
            modules => [auth_audit_logger]
        }
        % Other auth-related services will be added here
    ],
    {ok, {SupFlags, ChildSpecs}}.
