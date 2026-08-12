# HelixDB v3 JSON Wire Reference

This reference describes the direct request produced by the forthcoming v3 SDKs.
The source of truth is the `helix-ast` crate under
[`HelixDB/helix-db`](https://github.com/HelixDB/helix-db/tree/main/crates/ast).

## Envelope

```json
{
  "request_type": "read",
  "query_name": "optional_diagnostic_name",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
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
      ],
      "returns": ["users"]
    }
  }
}
```

| Field | Required | Shape |
|---|---:|---|
| `request_type` | yes | lowercase `"read"` or `"write"` |
| `query_name` | no | non-empty string or `null` |
| `query` | yes | `{ "read": ReadBatch }` or `{ "write": WriteBatch }` |
| `parameters` | no | object of JSON runtime values |
| `parameter_types` | no | object of v3 parameter type descriptors |

The batch variant must match `request_type`, and every batch must contain at
least one entry.

## Batches and entries

A batch contains entries in execution order and the variable names to return:

```json
{
  "read": {
    "entries": [
      {
        "query": {
          "name": "users",
          "root": {
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
    ],
    "returns": ["users"]
  }
}
```

`name` is optional in the underlying AST but should be present for normal `varAs`
entries. `condition` is also optional:

```json
{
  "query": {
    "name": "created",
    "condition": { "var_empty": "existing" },
    "root": {
      "add_n": {
        "label": "User",
        "properties": []
      }
    }
  }
}
```

The other entry form repeats a body for each object in a top-level array parameter:

```json
{
  "for_each": {
    "param": "users",
    "body": [
      {
        "query": {
          "name": "created",
          "root": {
            "add_n": {
              "label": "User",
              "properties": []
            }
          }
        }
      }
    ]
  }
}
```

Batch conditions serialize as `var_not_empty`, `var_empty`, `var_min_size`, or the
unit string `"prev_not_empty"`.

## Recursive operation encoding

`AstNode` is an externally tagged, `snake_case` enum. A source has no `input`:

```json
{
  "nodes": {
    "reference": { "ids": [0, 1] }
  }
}
```

```json
{
  "nodes_where": {
    "predicate": {
      "eq": {
        "left": { "property": "$label" },
        "right": { "constant": { "string": "User" } }
      }
    }
  }
}
```

Each following operation wraps the prior node under `input`:

```json
{
  "value_map": {
    "input": {
      "limit": {
        "input": {
          "out": {
            "input": {
              "nodes": {
                "reference": { "var": "user" }
              }
            },
            "label": "FOLLOWS"
          }
        },
        "count": { "literal": 25 }
      }
    },
    "properties": ["$id", "name"]
  }
}
```

Common read nodes:

| Builder idea | JSON variant | Important fields |
|---|---|---|
| node source | `nodes` | `reference` |
| indexed/filterable node source | `nodes_where` | `predicate` |
| edge source | `edges`, `edges_where` | `reference` or `predicate` |
| traverse | `out`, `in`, `both` | `input`, optional `label` |
| edge traversal | `out_e`, `in_e`, `both_e` | `input`, optional `label` |
| edge to node | `out_n`, `in_n`, `other_n` | `input` |
| filter | `where` | `input`, `predicate` |
| bound stream | `limit`, `range`, `skip` | `input` plus bound fields |
| deduplicate | `dedup` | `input` |
| project properties | `value_map` | `input`, `properties` |
| structured projection | `project` | `input`, `projections` |
| aggregate | `count`, `exists`, `aggregate` | `input` |
| order | `order_by`, `order_by_multiple` | `input` plus order fields |
| vector search | `vector_search_nodes`, `vector_search_edges` | label, property, query vector, `k`, optional tenant |
| text search | `text_search_nodes`, `text_search_edges` | label, property, query text, `k`, optional tenant |
| restricted text search | `text_search_nodes_within`, `text_search_edges_within` | `input`, label, property, query text, `k`, optional tenant |

Restricted text search is an exact BM25 prefilter over unique input IDs. It
returns at most `k`, orders by score descending then entity ID ascending, and
keeps tenant-partition BM25 statistics. The selected input row keeps bindings,
path, and sack and receives `$score`. Empty input skips the index; wrong-kind
input or more than 1,000,000 unique candidates is a query error.

Common write nodes:

| Builder idea | JSON variant | Important fields |
|---|---|---|
| add node | `add_n` | optional `input`, `label`, ordered `properties` |
| add edge | `add_e` | `input`, `label`, `to`, ordered `properties` |
| set property | `set_property` | `input`, `property`, `value` |
| drop current elements | `drop` | `input` |
| create index | `create_index` | `spec` |
| drop index | `drop_index` | `name` |

Use the SDK builders when a less-common node is needed. Serialize with
`toQueryJson`/`to_query_json` or the Rust/Go JSON encoder and treat that output as
canonical rather than guessing a field.

## References

`NodeRef` and `EdgeRef` are `snake_case` variants:

```json
{
  "reference": { "var": "alice" }
}
```

```json
{
  "reference": { "ids": [0, 1] }
}
```

```json
{
  "reference": { "param": "user_ids" }
}
```

## Values and inputs

`PropertyValue` values are tagged:

```json
{
  "string": "Alice"
}
```

```json
{
  "i64": 25
}
```

```json
{
  "f64_array": [0.1, 0.2, 0.3]
}
```

`PropertyInput` distinguishes a literal value from an expression:

```json
{
  "value": { "string": "Alice" }
}
```

```json
{
  "expr": { "param": "name" }
}
```

Properties on `add_n` and `add_e` are ordered pairs:

```json
{
  "properties": [
    ["name", { "value": { "string": "Alice" } }],
    ["active", { "value": { "bool": true } }]
  ]
}
```

## Predicates

Predicates are expression trees, not positional arrays:

```json
{
  "eq": {
    "left": { "property": "status" },
    "right": { "constant": { "string": "active" } }
  }
}
```

```json
{
  "and": {
    "predicates": [
      {
        "eq": {
          "left": { "property": "$label" },
          "right": { "constant": { "string": "User" } }
        }
      },
      {
        "gte": {
          "left": { "property": "age" },
          "right": { "param": "minimum_age" }
        }
      }
    ]
  }
}
```

Use `constant` for a literal, `param` for a runtime parameter, and `property` for the
current element's property.

## Parameter schemas

Scalar schema names include `string`, `i64`, `f64`, `bool`, `date_time`, and `bytes`.
Arrays and objects use their structured schema form as serialized by the SDK. Keep
`parameters` and `parameter_types` aligned.

```json
{
  "parameters": {
    "minimum_age": 18
  },
  "parameter_types": {
    "minimum_age": "i64"
  }
}
```

## Responses

The server returns one top-level member per returned batch name. Nodes and edges are
normalized user-facing objects.

```json
{
  "users": [
    { "$id": 0, "name": "Alice" },
    { "$id": 1, "name": "Bob" }
  ]
}
```

Do not document internal `current`/`bindings` rows as the public response.

## Validation checklist

- Parse every complete `json` fence.
- Confirm `request_type` and batch variant match.
- Confirm every returned name exists in an entry.
- Confirm every non-source operation has the correct nested `input`.
- Confirm all enum tags are `snake_case`.
- Compare hand-written JSON with an SDK serializer for the same query.
- Run applicable requests against `ghcr.io/helixdb/helixdb:v0.0.3`.
