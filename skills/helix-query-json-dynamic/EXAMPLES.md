# HelixDB v3 JSON Examples

Direct request bodies for `POST /v2/query`, using the same nested AST as the v3 SDKs.

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

Response from a clean `ghcr.io/helixdb/helixdb:v0.0.16` instance:

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

## Upsert by a unique key

Create the unique index once (build-time semantics: REFERENCE.md, Index specs):

```json
{
  "request_type": "write",
  "query_name": "create_user_id_index",
  "query": {
    "write": {
      "entries": [
        {
          "query": {
            "name": "index",
            "root": {
              "create_index": {
                "spec": { "node_equality": { "label": "User", "property": "userId", "unique": true } },
                "if_not_exists": true
              }
            }
          }
        }
      ],
      "returns": ["index"]
    }
  }
}
```

The response is a receipt, e.g.
`{"index": {"kind": "accepted", "operation_id": "07070707-0707-0707-0707-070707070707", "index_id": "1", "generation": "1"}}`.
Poll until `status` is `succeeded`:

```json
{
  "request_type": "read",
  "query_name": "index_status",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "status",
            "root": { "get_index_operation": { "operation_id": "07070707-0707-0707-0707-070707070707" } }
          }
        }
      ],
      "returns": ["status"]
    }
  }
}
```

On `blocked`, fix the data its `blocker_code` names (for `uniqueness_violation`, the
existing duplicates) and send `{"retry_index_operation": {"operation_id": "..."}}` in a
write request. Then upsert in one atomic write batch:

```json
{
  "request_type": "write",
  "query_name": "upsert_user",
  "query": {
    "write": {
      "entries": [
        {
          "query": {
            "name": "existing",
            "root": {
              "nodes_where": {
                "predicate": {
                  "and": {
                    "predicates": [
                      { "eq": { "left": { "property": "$label" }, "right": { "constant": { "string": "User" } } } },
                      { "eq": { "left": { "property": "userId" }, "right": { "param": "user_id" } } }
                    ]
                  }
                }
              }
            }
          }
        },
        {
          "query": {
            "name": "updated",
            "condition": { "var_not_empty": "existing" },
            "root": {
              "set_property": {
                "input": { "nodes": { "reference": { "var": "existing" } } },
                "name": "name",
                "value": { "expr": { "param": "name" } }
              }
            }
          }
        },
        {
          "query": {
            "name": "created",
            "condition": { "var_empty": "existing" },
            "root": {
              "add_n": {
                "label": "User",
                "properties": [
                  ["userId", { "expr": { "param": "user_id" } }],
                  ["name", { "expr": { "param": "name" } }]
                ]
              }
            }
          }
        }
      ],
      "returns": ["updated", "created"]
    }
  },
  "parameters": { "user_id": "u-1", "name": "Ada" }
}
```

One of `updated` / `created` is `[{"$id": N}]`, the other `[]`. A racing loser gets
`409 unique_constraint_violation` (`retryable: false`) or `409 transaction_conflict`
(`retryable: true`); re-run the upsert once and it takes the update branch.

## Optional neighbor (OPTIONAL MATCH)

`optional` passes the input row through when its branch is empty, so read the optional
side through a binding (a missing binding omits its key). `bind` and `project_bindings`
are read-only.

```json
{
  "request_type": "read",
  "query_name": "users_with_employer",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "rows",
            "root": {
              "project_bindings": {
                "input": {
                  "optional": {
                    "input": {
                      "bind": {
                        "input": {
                          "nodes_where": {
                            "predicate": { "eq": { "left": { "property": "$label" }, "right": { "constant": { "string": "User" } } } }
                          }
                        },
                        "name": "user"
                      }
                    },
                    "traversal": {
                      "root": {
                        "bind": {
                          "input": {
                            "has_label": {
                              "input": { "out": { "input": "context", "label": "WORKS_AT" } },
                              "label": "Company"
                            }
                          },
                          "name": "employer"
                        }
                      }
                    }
                  }
                },
                "projections": [
                  { "property": { "target": { "binding": "user" }, "source": "name", "alias": "name" } },
                  { "property": { "target": { "binding": "employer" }, "source": "name", "alias": "employer" } }
                ],
                "distinct": false
              }
            }
          }
        }
      ],
      "returns": ["rows"]
    }
  }
}
```

```json
{ "rows": [{ "name": "Ada", "employer": "Acme" }, { "name": "Bob" }] }
```

## Eventual search consistency

A read trading freshness of unpublished vector/text work for never failing with
`index_backpressure`:

```json
{
  "request_type": "read",
  "query_name": "similar_docs",
  "search_consistency": "eventual",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "hits",
            "root": {
              "value_map": {
                "input": {
                  "vector_search_nodes": {
                    "label": "Doc",
                    "property": "embedding",
                    "query_vector": { "expr": { "param": "vector" } },
                    "k": { "literal": 10 }
                  }
                },
                "properties": ["$id", "title", "$distance"]
              }
            }
          }
        }
      ],
      "returns": ["hits"]
    }
  },
  "parameters": { "vector": [0.1, 0.8, 0.2] }
}
```

## Cypher instead of the operation tree

A statement in the Cypher profile goes to `POST /v2/cypher`:

```json
{
  "query": "MATCH (u:User) OPTIONAL MATCH (u)-[:WORKS_AT]->(c:Company) RETURN u.name AS name, c.name AS employer ORDER BY name",
  "parameters": {},
  "query_name": "users_with_employer"
}
```

```json
{ "columns": ["name", "employer"], "rows": [["Ada", "Acme"], ["Bob", null]] }
```

## Invalid legacy shapes

Intentionally invalid (shown as `text` so JSON validation skips them):

```text
{"queries":[{"Query":{"steps":["Count"]}}],"returns":["count"]}
```

```text
{"request_type":"READ","query":{"read":{"entries":[],"returns":[]}}}
```

```text
{"request_type":"read","queries.json":{}}
```

For a shape not covered here, use an SDK serializer; the Rust, TypeScript, Python and Go
builders serialize to the same JSON.

## Interpret A Query Failure

Both of these are HTTP 409; only the first is worth resending:

```json
{ "error": "transaction_conflict", "msg": "<diagnostic>", "retryable": true }
```

```json
{ "error": "unique_constraint_violation", "msg": "<diagnostic>", "retryable": false }
```

`retryable: false` on a 409 means the database's state rejects the request: report the
duplicate or fix the state. Rules: SKILL.md, Failure envelope.
