import test from "node:test";
import assert from "node:assert/strict";
import { setMessages } from "../js/lib/i18n.js";
import { partOfDay, firstNameOf, greetingText, dateLabel, initialOf } from "../js/lib/greeting.js";

setMessages({});

test("partOfDay boundaries", () => {
  const exp = { 0: "evening", 4: "evening", 5: "morning", 11: "morning", 12: "afternoon", 16: "afternoon", 17: "evening", 23: "evening" };
  for (const [h, part] of Object.entries(exp)) assert.equal(partOfDay(Number(h)), "Good " + part);
});

test("firstNameOf variants", () => {
  assert.equal(firstNameOf({ fullName: "Paco Alaez", userId: "p@x.es" }), "Paco");
  assert.equal(firstNameOf({ fullName: "p@x.es", userId: "p@x.es" }), "P");
  assert.equal(firstNameOf({ fullName: "", userId: "ana.lopez@x.es" }), "Ana");
  assert.equal(firstNameOf({ fullName: "", userId: "Guest" }), null);
  assert.equal(firstNameOf({ fullName: "", userId: "" }), null);
});

test("greetingText composes with and without a name", () => {
  const d = new Date(2026, 9, 1, 9, 0);
  assert.equal(greetingText(d, "Paco"), "Good morning, Paco.");
  assert.equal(greetingText(d, null), "Good morning.");
  setMessages({ "Good morning": "Buenos días" });
  assert.equal(greetingText(d, "Paco"), "Buenos días, Paco.");
  setMessages({});
});

test("dateLabel", () => {
  assert.equal(dateLabel(new Date(2026, 9, 1), "en"), "Thursday · 1 October");
});

test("initialOf", () => {
  assert.equal(initialOf({ fullName: "paco", userId: "x" }), "P");
  assert.equal(initialOf({ fullName: "", userId: "ana@x" }), "A");
  assert.equal(initialOf({ fullName: "", userId: "" }), "U");
});
