%%%-------------------------------------------------------------------
%% @doc crm_backend public API
%% @end
%%%-------------------------------------------------------------------

-module(crm_backend_app).

-behaviour(application).

-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    crm_backend_sup:start_link().

stop(_State) ->
    ok.

%% internal functions
