// This test is copied into the exact Cosign v3.1.2 source in an isolated CI job.
// It exercises its real statement generator; it does not sign or publish anything.
package attestation

import (
    "bytes"
    "encoding/json"
    "os"
    "reflect"
    "testing"
)

func TestCodestraProvenanceRoundTrip(t *testing.T) {
    input, err := os.ReadFile(os.Getenv("CODESTRA_COSIGN_PREDICATE"))
    if err != nil { t.Fatal(err) }
    var expected map[string]any
    if err := json.Unmarshal(input, &expected); err != nil { t.Fatal(err) }
    predicateType := os.Getenv("CODESTRA_PROVENANCE_TYPE")
    if predicateType != "https://slsa.dev/provenance/v1" { t.Fatal("unexpected workflow predicate type") }
    for _, kind := range []string{predicateType, "slsaprovenance"} {
        generated, err := GenerateStatement(GenerateOpts{
            Predicate: bytes.NewReader(input), Type: kind,
            Digest: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            Repo: "ghcr.io/appolon1908-hue/example-service",
        })
        if err != nil { t.Fatal(err) }
        encoded, err := json.Marshal(generated)
        if err != nil { t.Fatal(err) }
        var decoded map[string]any
        if err := json.Unmarshal(encoded, &decoded); err != nil { t.Fatal(err) }
        output := os.Getenv("CODESTRA_COSIGN_OUTPUT")
        if kind == predicateType {
            if decoded["predicateType"] != predicateType || !reflect.DeepEqual(decoded["predicate"], expected) {
                t.Fatal("Cosign did not preserve the complete v1 predicate")
            }
        } else {
            if reflect.DeepEqual(decoded["predicate"], expected) { t.Fatal("legacy regression was not reproduced") }
            output += ".legacy"
        }
        if err := os.WriteFile(output, encoded, 0600); err != nil { t.Fatal(err) }
    }
}
