# Rakuten RMS Coupon API — XML Contract

Wire-level reference for the `/es/1.0/coupon/*` endpoints.
Ported from JakeJP/Rakuten.RMS.Api and Rakuten RMS WEB API documentation.

## Base URL

```
https://api.rms.rakuten.co.jp/es/1.0
```

## Authentication

```
Authorization: ESA <base64(serviceSecret:licenseKey)>
Content-Type: application/xml; charset=utf-8
Accept: application/xml
```

## Common XML Envelope

### Request
```xml
<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>   <!-- or couponUpdateRequest, couponDeleteRequest -->
    <coupon>
      <!-- fields... -->
    </coupon>
  </couponIssueRequest>
</request>
```

### Success Response
```xml
<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <interfaceId>coupon.issue</interfaceId>
    <systemStatus>OK</systemStatus>
    <message></message>
    <requestId>abc-123</requestId>
  </status>
  <!-- endpoint-specific content -->
</result>
```

### Error Response
```xml
<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <interfaceId>coupon.issue</interfaceId>
    <systemStatus>NG</systemStatus>
    <message>Validation error</message>
    <requestId>abc-123</requestId>
  </status>
  <errors>
    <error>
      <code>COUPON-001</code>
      <message>Coupon name is too long</message>
    </error>
  </errors>
</result>
```

---

## POST /es/1.0/coupon/issue — Issue Coupon

### Request Body

```xml
<?xml version="1.0" encoding="UTF-8"?>
<request>
  <couponIssueRequest>
    <coupon>
      <couponName>サマーセール</couponName>
      <couponCaption>全品10%OFF</couponCaption>
      <couponStartDate>2026-07-01T00:00:00+09:00</couponStartDate>
      <couponEndDate>2026-07-31T23:59:59+09:00</couponEndDate>
      <couponIssueCount>1000</couponIssueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>10</discountFactor>
      <combineFlag>0</combineFlag>
      <displayFlag>1</displayFlag>
      <memberMaxCount>1</memberMaxCount>
      <items>
        <item>
          <itemUrl>https://item.rakuten.co.jp/shop/item123/</itemUrl>
        </item>
      </items>
      <otherConditions>
        <otherCondition>
          <conditionTypeCode>RS003</conditionTypeCode>
          <startValue>3000</startValue>
        </otherCondition>
      </otherConditions>
    </coupon>
  </couponIssueRequest>
</request>
```

### Element Reference

| XML Element | Type | Required | Max Length | Notes |
|------------|------|----------|-----------|-------|
| `couponName` | string | ✅ | 50 | Coupon display name |
| `couponCaption` | string | ✅ | 30 | Short description |
| `couponStartDate` | dateTime | ✅ | — | ISO 8601 + JST offset |
| `couponEndDate` | dateTime | ✅ | — | Must be after startDate |
| `couponIssueCount` | int | ✅ | — | Number to issue, ≥1 |
| `itemType` | int | ✅ | — | 1=single, 3=multiple, 4=order, 5=free shipping |
| `discountType` | int | ✅ | — | 1=fixed yen, 2=percentage, 4=free shipping |
| `discountFactor` | int | ✅ | — | Yen amount or percentage (1-99) |
| `combineFlag` | int | ✅ | — | 0=no, 1=yes |
| `displayFlag` | int | — | — | 0=hidden, 1=visible (default 1) |
| `couponImageUrl` | string | — | — | Image URL |
| `memberMaxCount` | int | — | — | Max uses/member (default 1) |
| `multiRankCond/rankCond` | int[] | — | — | 0=none, 1=Regular, 2=Silver, 3=Gold, 4=Platinum, 5=Diamond |
| `genderCond` | int | — | — | 0=unspec, 1=male, 2=female |
| `ageRangeCond` | int | — | — | Target age |
| `multiPrefectureCond/prefectureCond` | string[] | — | — | Prefecture code |
| `birthmonthCond` | int | — | — | 0=unspec, 1-12 |
| `items/item/itemUrl` | string[] | — | — | Max 3000 items. Required for itemType 1,3 |
| `otherConditions/otherCondition` | complex[] | — | — | See OtherCondition below |

### OtherCondition

| XML Element | Type | Notes |
|------------|------|-------|
| `conditionTypeCode` | string | RS001=device(0=PC,1=Mobile), RS002=sales(0=Normal), RS003=min amount(yen), RS004=min quantity |
| `startValue` | string | RS003: 1-999999999, RS004: 0-999999999 |

### Success Response

```xml
<result>
  <couponIssueResult>
    <couponCode>ABC123DEF456</couponCode>
    <pcGetUrl>https://coupon.rakuten.co.jp/get/ABC123DEF456</pcGetUrl>
  </couponIssueResult>
</result>
```

| Element | Type | Notes |
|---------|------|-------|
| `couponCode` | string | Unique issued coupon code |
| `pcGetUrl` | string | URL customers visit to claim coupon |

---

## POST /es/1.0/coupon/update — Update Coupon

Same XML structure as issue, but includes `<couponCode>` element and uses `<couponUpdateRequest>` wrapper.

```xml
<request>
  <couponUpdateRequest>
    <coupon>
      <couponCode>ABC123DEF456</couponCode>
      <!-- ... same fields as issue ... -->
    </coupon>
  </couponUpdateRequest>
</request>
```

Response: Empty `<result>` with `<systemStatus>OK</systemStatus>` on success.

---

## POST /es/1.0/coupon/delete — Delete Coupon

### Request

```xml
<request>
  <couponDeleteRequest>
    <coupon>
      <couponCode>ABC123DEF456</couponCode>
    </coupon>
  </couponDeleteRequest>
</request>
```

### Response

Empty `<result>` with `<systemStatus>OK</systemStatus>` on success. May return error if coupon is already deleted or code is invalid.

---

## GET /es/1.0/coupon/search — Search/Get Coupons

### Query Parameters

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `couponCode` | string | — | Exact match for single lookup |
| `couponName` | string | — | Partial match |
| `itemUrl` | string | — | Filter by target item URL |
| `couponStartDate` | dateTime | — | Active from date |
| `couponEndDate` | dateTime | — | Active until date |
| `hits` | int | — | Results per page |
| `page` | int | — | Page number (1-indexed) |

### Success Response

```xml
<result>
  <allCount>42</allCount>
  <coupons>
    <coupon>
      <couponCode>ABC123</couponCode>
      <couponName>サマーセール</couponName>
      <couponCaption>全品10%OFF</couponCaption>
      <couponStartDate>2026-07-01T00:00:00+09:00</couponStartDate>
      <couponEndDate>2026-07-31T23:59:59+09:00</couponEndDate>
      <couponIssueCount>1000</couponIssueCount>
      <itemType>4</itemType>
      <discountType>2</discountType>
      <discountFactor>10</discountFactor>
      <combineFlag>0</combineFlag>
      <displayFlag>1</displayFlag>
      <!-- ... all coupon fields ... -->
    </coupon>
    <coupon>
      <!-- ... more coupons ... -->
    </coupon>
  </coupons>
</result>
```

| Element | Type | Notes |
|---------|------|-------|
| `allCount` | int | Total matching coupons across all pages |
| `coupons/coupon` | array | Array of Coupon objects |

## HTTP Status Codes

| Status | Meaning | Retryable |
|--------|---------|-----------|
| 200 | Success | — |
| 400 | Bad request / validation error | No |
| 401 | Invalid credentials / expired license | No |
| 404 | Not found (search returns empty) | No |
| 429 | Rate limited | **Yes** |
| 500 | Server error | **Yes** |
| 503 | Service unavailable | **Yes** |

## Japanese Date Format

All dates must use ISO 8601 with JST offset:
```
2026-07-01T00:00:00+09:00
```

Not: `2026-07-01` (missing time), `2026-07-01T00:00:00Z` (UTC).
