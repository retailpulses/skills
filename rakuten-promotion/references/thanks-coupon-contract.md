# Rakuten RMS Thanks Coupon API — XML Contract

Wire-level reference for the `/es/1.0/thankscoupon*` endpoints.
Thanks coupons are automatically granted to customers who meet predefined conditions
(total purchase price, grant period, service use history).

Ported from JakeJP/Rakuten.RMS.Api.

## Base URL

```
https://api.rms.rakuten.co.jp/es/1.0
```

## Authentication

Same as CouponAPI:
```
Authorization: ESA <base64(serviceSecret:licenseKey)>
Content-Type: application/xml; charset=utf-8
```

---

## POST /es/1.0/thankscoupon — Issue Thanks Coupon

### Request Body

```xml
<?xml version="1.0" encoding="UTF-8"?>
<request>
  <thanksCoupon>
    <couponName>ご愛顧感謝クーポン</couponName>
    <couponCaption>次回10%OFF</couponCaption>
    <discountType>2</discountType>
    <discountFactor>10</discountFactor>
    <couponTerm>30</couponTerm>
    <memberAvailMaxCount>1</memberAvailMaxCount>
    <combineFlag>0</combineFlag>
    <couponImage>https://image.rakuten.co.jp/shop/coupon.jpg</couponImage>
    <couponUnavailableTerm>0</couponUnavailableTerm>
    <thanksOtherConditions>
      <thanksOtherCondition>
        <conditionTypeCode>RS003</conditionTypeCode>
        <startValue>5000</startValue>
      </thanksOtherCondition>
    </thanksOtherConditions>
    <thanksAutoGetConditions>
      <thanksAutoGetCondition>
        <getCondCd>totalPrice</getCondCd>
        <startValue>10000</startValue>
      </thanksAutoGetCondition>
      <thanksAutoGetCondition>
        <getCondCd>grantTerm</getCondCd>
        <startValue>2026-06-01T00:00:00+09:00</startValue>
        <endValue>2026-06-30T23:59:59+09:00</endValue>
      </thanksAutoGetCondition>
    </thanksAutoGetConditions>
  </thanksCoupon>
</request>
```

### Element Reference

| XML Element | Type | Required | Notes |
|------------|------|----------|-------|
| `couponName` | string | ✅ | Max 50 chars |
| `couponCaption` | string | ✅ | Max 30 chars |
| `discountType` | int | ✅ | 1=fixed yen, 2=percentage, 4=free shipping |
| `discountFactor` | int | ✅ | Yen amount or percentage (1-99) |
| `couponTerm` | int | ✅ | Validity period in days from grant date |
| `memberAvailMaxCount` | int | ✅ | Max uses per member, ≥1 |
| `combineFlag` | int | ✅ | 0=no combine, 1=can combine |
| `couponImage` | string | — | Image URL |
| `couponUnavailableTerm` | int | — | Days before coupon becomes usable |
| `thanksOtherConditions` | complex[] | — | Usage conditions (same as standard coupon) |
| `thanksAutoGetConditions` | complex[] | ✅ | Grant criteria (see below) |

### Success Response

```xml
<result>
  <thanksCouponId>123456</thanksCouponId>
</result>
```

Returns the numeric thanks coupon ID.

---

## PUT /es/1.0/thankscoupon/{id} — Update Thanks Coupon

Same XML structure as issue. Send to `/es/1.0/thankscoupon/123456`.

Returns `thanksCouponId` on success.

---

## PUT /es/1.0/thankscoupon/{id}/issuestatus/stop — Stop Thanks Coupon

No request body. Stops distribution of the thanks coupon early.

Returns `thanksCouponId` on success.

---

## GET /es/1.0/thankscoupon/{id} — Get Thanks Coupon

Returns full thanks coupon object:

```xml
<result>
  <thanksCoupon>
    <thanksCouponId>123456</thanksCouponId>
    <couponName>ご愛顧感謝クーポン</couponName>
    <couponCaption>次回10%OFF</couponCaption>
    <discountType>2</discountType>
    <discountFactor>10</discountFactor>
    <couponTerm>30</couponTerm>
    <memberAvailMaxCount>1</memberAvailMaxCount>
    <combineFlag>0</combineFlag>
    <shopId>12345</shopId>
    <shopName>テスト商店</shopName>
    <shopUrl>https://www.rakuten.co.jp/shop/</shopUrl>
    <!-- ... all thanks coupon fields ... -->
  </thanksCoupon>
</result>
```

HTTP 404 if not found.

---

## GET /es/1.0/thankscoupon — Search Thanks Coupons

### Query Parameters

| Parameter | Type | Notes |
|-----------|------|-------|
| `issueStatus` | int | 3=before period, 4=in period, 5=stopped, 6=ended |
| `grantStartDate` | dateTime | Filter by grant start |
| `grantEndDate` | dateTime | Filter by grant end |
| `regDate` | dateTime | Filter by registration date |
| `hits` | int | Per page (max 100, default 30) |
| `page` | int | 1-indexed (default 1) |

### Success Response

```xml
<result>
  <allCount>15</allCount>
  <thanksCoupons>
    <thanksCoupon>
      <!-- ... thanks coupon fields ... -->
    </thanksCoupon>
  </thanksCoupons>
</result>
```

### ⚠️ 404 on Empty Results

If no thanks coupons match the search criteria, the API returns **HTTP 404** (not 200 with empty array). This is documented Rakuten behavior — the TypeScript client handles this by returning `null`.

---

## ThanksAutoGetCondition Reference

These conditions determine when a thanks coupon is automatically granted to a customer.

| `getCondCd` | Required | Description | `startValue` | `endValue` |
|------------|----------|-------------|-------------|-----------|
| `totalPrice` | ✅ | Minimum total purchase price to trigger grant | Price in yen (e.g., "10000") | — |
| `grantTerm` | ✅ | Period during which purchases count toward the condition | Start date (ISO 8601) | End date (ISO 8601) |
| `serviceUseHistory` | — | Service use history requirement | Service code | — |

`compOperatorCd` (comparison operator) is optional and rarely used.

---

## HTTP Status Codes

| Status | Meaning | Notes |
|--------|---------|-------|
| 200 | Success | — |
| 400 | Validation error | Check field values |
| 401 | Auth error | Check serviceSecret/licenseKey |
| 404 | Not found **or** no search results | Client returns `null` for search |
| 429 | Rate limited | Retry with backoff |
| 5xx | Server error | Retry with backoff |
