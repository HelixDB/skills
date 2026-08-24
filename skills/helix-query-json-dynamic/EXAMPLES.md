# HelixDB v3 JSON Examples

These are direct request bodies for `POST /v2/query`. They use the same nested AST as
the published v3 SDKs.

## Count nodes by label

```json
{
  "request_type": "read",
  "query_name": "node_count",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "node_count",
            "root": {
              "count": {
                "input": {
                  "nodes_where": {
                    "predicate": {
                      "eq": {
                        "left": { "property": "$label" },
                        "right": { "constant": { "string": "User" } }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      ],
      "returns": ["node_count"]
    }
  }
}
```

Expected shape:

```json
{
  "node_count": 0
}
```

## Filter, limit, and project

```json
{
  "request_type": "read",
  "query_name": "active_users",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
              "value_map": {
                "input": {
                  "limit": {
                    "input": {
                      "where": {
                        "input": {
                          "nodes_where": {
                            "predicate": {
                              "eq": {
                                "left": { "property": "$label" },
                                "right": { "constant": { "string": "User" } }
                              }
                            }
                          }
                        },
                        "predicate": {
                          "eq": {
                            "left": { "property": "status" },
                            "right": { "constant": { "string": "active" } }
                          }
                        }
                      }
                    },
                    "count": { "literal": 25 }
                  }
                },
                "properties": ["$id", "name"]
              }
            }
          }
        }
      ],
      "returns": ["users"]
    }
  }
}
```

## Parameterized query

```json
{
  "request_type": "read",
  "query_name": "find_users",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
              "value_map": {
                "input": {
                  "limit": {
                    "input": {
                      "where": {
                        "input": {
                          "nodes_where": {
                            "predicate": {
                              "eq": {
                                "left": { "property": "$label" },
                                "right": { "constant": { "string": "User" } }
                              }
                            }
                          }
                        },
                        "predicate": {
                          "eq": {
                            "left": { "property": "tenantId" },
                            "right": { "param": "tenant_id" }
                          }
                        }
                      }
                    },
                    "count": { "expr": { "param": "limit" } }
                  }
                },
                "properties": ["$id", "name", "tenantId"]
              }
            }
          }
        }
      ],
      "returns": ["users"]
    }
  },
  "parameters": {
    "tenant_id": "acme",
    "limit": 25
  },
  "parameter_types": {
    "tenant_id": "string",
    "limit": "i64"
  }
}
```

## Write two nodes, connect them, and read through the edge

```json
{
  "request_type": "write",
  "query_name": "write_users",
  "query": {
    "write": {
      "entries": [
        {
          "query": {
            "name": "alice",
            "root": {
              "add_n": {
                "label": "User",
                "properties": [
                  ["name", { "value": { "string": "Alice" } }]
                ]
              }
            }
          }
        },
        {
          "query": {
            "name": "bob",
            "root": {
              "add_n": {
                "label": "User",
                "properties": [
                  ["name", { "value": { "string": "Bob" } }]
                ]
              }
            }
          }
        },
        {
          "query": {
            "name": "follow",
            "root": {
              "add_e": {
                "input": {
                  "nodes": { "reference": { "var": "alice" } }
                },
                "label": "FOLLOWS",
                "to": { "var": "bob" },
                "properties": [
                  ["since", { "value": { "string": "2026-07-24" } }]
                ]
              }
            }
          }
        },
        {
          "query": {
            "name": "friends",
            "root": {
              "value_map": {
                "input": {
                  "out": {
                    "input": {
                      "nodes": { "reference": { "var": "alice" } }
                    },
                    "label": "FOLLOWS"
                  }
                },
                "properties": ["$id", "name"]
              }
            }
          }
        }
      ],
      "returns": ["alice", "bob", "friends"]
    }
  }
}
```

Expected response from a clean `ghcr.io/helixdb/helixdb:v0.0.4` instance:

```json
{
  "alice": [{ "$id": 0 }],
  "bob": [{ "$id": 1 }],
  "friends": [{ "$id": 1, "name": "Bob" }]
}
```

## Traverse from a previous entry

```json
{
  "request_type": "read",
  "query_name": "friends",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "user",
            "root": {
              "nodes_where": {
                "predicate": {
                  "eq": {
                    "left": { "property": "username" },
                    "right": { "constant": { "string": "alice" } }
                  }
                }
              }
            }
          }
        },
        {
          "query": {
            "name": "friends",
            "root": {
              "value_map": {
                "input": {
                  "limit": {
                    "input": {
                      "dedup": {
                        "input": {
                          "out": {
                            "input": {
                              "nodes": {
                                "reference": { "var": "user" }
                              }
                            },
                            "label": "FOLLOWS"
                          }
                        }
                      }
                    },
                    "count": { "literal": 25 }
                  }
                },
                "properties": ["$id", "username"]
              }
            }
          }
        }
      ],
      "returns": ["friends"]
    }
  }
}
```

## Structured projection

```json
{
  "request_type": "read",
  "query_name": "project_users",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
              "project": {
                "input": {
                  "nodes_where": {
                    "predicate": {
                      "eq": {
                        "left": { "property": "$label" },
                        "right": { "constant": { "string": "User" } }
                      }
                    }
                  }
                },
                "projections": [
                  {
                    "property": {
                      "source": "$id",
                      "alias": "user_id"
                    }
                  },
                  {
                    "property": {
                      "source": "name",
                      "alias": "name"
                    }
                  }
                ]
              }
            }
          }
        }
      ],
      "returns": ["users"]
    }
  }
}
```

## Invalid legacy shapes

The following are intentionally invalid and shown as `text` so JSON validation does
not mistake them for supported requests:

```text
{"queries":[{"Query":{"steps":["Count"]}}],"returns":["count"]}
```

```text
{"request_type":"READ","query":{"read":{"entries":[],"returns":[]}}}
```

```text
{"request_type":"read","queries.json":{}}
```

Use an SDK serializer when constructing a shape not covered here. Equivalent builders
in the Rust, TypeScript, Python, and Go skills must serialize to the same JSON
structure.

## Interpret A Query Failure

Current servers return the stable code in `error` and the diagnostic in `msg`:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
```

```json
{
  "error": "transaction_conflict",
  "msg": "transaction commit conflicted with another writer"
}
```

Use the HTTP 409 plus `transaction_conflict` for classification. Reload current
state before rebuilding, then replay with bounded backoff only if the operation
is idempotent or protected by an idempotency key. Do not parse `msg`.

During a rolling upgrade, also accept the legacy shape:

```json
{
  "error": "transaction commit conflicted with another writer",
  "code": "transaction_conflict"
}
```

A defensive client may also preserve a noncanonical proxy shape:

```json
{
  "code": "external_error",
  "message": "upstream rejected the request",
  "details": { "request_id": "req_123" }
}
```

Decode canonical Helix, legacy Helix, then generic remote fields. Preserve
`details`, the raw body, and unknown codes, but do not call the generic shape
the gateway contract. An idempotent read may retry a 429 or temporary 5xx with
bounded backoff. For a 409 write conflict, reload current state before rebuilding
and replay only when safe; do not blindly retry writes.
