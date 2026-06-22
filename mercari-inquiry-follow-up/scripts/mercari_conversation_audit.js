() => {
  const DISCLAIMER = "本メッセージはご放念ください";
  const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
  const sellerNodes = Array.from(
    document.querySelectorAll('[data-testid="talk-room-message-text"]'),
  );

  let host = null;
  for (const sellerNode of sellerNodes) {
    let node = sellerNode;
    for (let depth = 0; depth < 8 && node.parentElement; depth += 1) {
      const parent = node.parentElement;
      const messageChildren = Array.from(parent.children).filter((child) =>
        child.querySelector(
          '[data-testid="talk-room-message-text"], [data-testid="products"], [data-testid="product-name"]',
        ),
      );
      if (messageChildren.length >= 2 && !parent.querySelector("textarea")) {
        host = parent;
        break;
      }
      node = parent;
    }
    if (host) break;
  }

  const sequence = host
    ? Array.from(host.children)
        .map((child) => {
          const seller = child.querySelector(
            '[data-testid="talk-room-message-text"]',
          );
          if (seller) {
            return { role: "seller", text: clean(seller.innerText) };
          }
          const parts = Array.from(child.querySelectorAll("p"))
            .map((node) => clean(node.innerText))
            .filter(Boolean);
          if (!parts.length) return null;
          return { role: "customer", text: parts.join(" | ") };
        })
        .filter((message) => message && message.text)
    : [];

  const firstIsFollowup =
    sequence[0]?.role === "seller" && sequence[0].text.includes(DISCLAIMER);
  const beforeFollowup = firstIsFollowup ? sequence.slice(1) : sequence;
  const latest = beforeFollowup[0] || null;
  const latestCustomer = beforeFollowup.find(
    (message) => message.role === "customer",
  );
  const latestSeller = beforeFollowup.find(
    (message) => message.role === "seller",
  );

  return {
    pageTitle: clean(document.title),
    replyBoxPresent: Boolean(document.querySelector("textarea")),
    followupAlreadyPresent: firstIsFollowup,
    messageCount: sequence.length,
    rolesNewestFirst: sequence.map((message) => message.role),
    preFollowupLatestRole: latest?.role || "unknown",
    latestCustomerText: (latestCustomer?.text || "").slice(0, 1200),
    latestSellerText: (latestSeller?.text || "").slice(0, 1200),
    chronologyGate:
      latest?.role === "customer"
        ? "unanswered_customer"
        : latest?.role === "seller"
          ? "semantic_answer_check_required"
          : "unknown",
  };
}
