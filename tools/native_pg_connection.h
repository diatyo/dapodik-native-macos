/* Local transport adapter for the isolated Dapodik cluster. Authentication is
 * still enforced by PostgreSQL. Application login/permissions are unchanged. */
#include <stdlib.h>
#include <string.h>
#include <libpq-fe.h>

static PGconn *dapodik_native_connect(const char *connstr) {
    const char *socket_path = getenv("DAPODIK_NATIVE_DB_SOCKET");
    if (!socket_path || !*socket_path) return PQconnectdb(connstr);
    char *error = NULL;
    PQconninfoOption *options = PQconninfoParse(connstr, &error);
    if (!options) {
        if (error) PQfreemem(error);
        return PQconnectdb(connstr);
    }
    const char *host = "", *port = "", *database = "", *user = "";
    size_t count = 0;
    for (PQconninfoOption *o = options; o->keyword; ++o) {
        ++count;
        if (!o->val) continue;
        if (!strcmp(o->keyword, "host")) host = o->val;
        if (!strcmp(o->keyword, "port")) port = o->val;
        if (!strcmp(o->keyword, "dbname")) database = o->val;
        if (!strcmp(o->keyword, "user")) user = o->val;
    }
    int local = (!strcmp(host, "localhost") || !strcmp(host, "127.0.0.1"))
        && !strcmp(port, "54532") && (!strcmp(user, "postgres") || !strcmp(user, "dapodik_user"))
        && (!strcmp(database, "pendataan") || !strcmp(database, "dapodik_app"));
    if (!local) { PQconninfoFree(options); return PQconnectdb(connstr); }
    const char **keys = calloc(count + 2, sizeof(char *));
    const char **values = calloc(count + 2, sizeof(char *));
    if (!keys || !values) {
        free(keys); free(values); PQconninfoFree(options);
        return PQconnectdb(connstr);
    }
    size_t index = 0;
    for (PQconninfoOption *o = options; o->keyword; ++o) {
        if (!o->val || !strcmp(o->keyword, "password")) continue;
        keys[index] = o->keyword;
        values[index++] = !strcmp(o->keyword, "host") ? socket_path : o->val;
    }
    PGconn *connection = PQconnectdbParams(keys, values, 0);
    free(keys); free(values); PQconninfoFree(options);
    return connection;
}
