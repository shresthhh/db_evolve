"""TPC-H as 22 parameterised templates.

Substitution parameters follow the TPC-H specification (clause 2.4.x "Substitution Parameters").
Two deliberate deviations, both so that every query has exactly one correct, ordered answer and
candidates can be checked by plain comparison:
  * ORDER BY clauses get a unique tiebreaker where the spec's ordering admits ties
    (Q3, Q5, Q10, Q11, Q18);
  * Q15 uses a CTE instead of CREATE VIEW / DROP VIEW.
"""
from __future__ import annotations

import datetime as dt
import re

TABLES = ["region", "nation", "supplier", "customer", "part", "partsupp", "orders", "lineitem"]

REGIONS = ["AFRICA", "AMERICA", "ASIA", "EUROPE", "MIDDLE EAST"]
NATIONS = {  # nation -> region
    "ALGERIA": "AFRICA", "ARGENTINA": "AMERICA", "BRAZIL": "AMERICA", "CANADA": "AMERICA",
    "EGYPT": "MIDDLE EAST", "ETHIOPIA": "AFRICA", "FRANCE": "EUROPE", "GERMANY": "EUROPE",
    "INDIA": "ASIA", "INDONESIA": "ASIA", "IRAN": "MIDDLE EAST", "IRAQ": "MIDDLE EAST",
    "JAPAN": "ASIA", "JORDAN": "MIDDLE EAST", "KENYA": "AFRICA", "MOROCCO": "AFRICA",
    "MOZAMBIQUE": "AFRICA", "PERU": "AMERICA", "CHINA": "ASIA", "ROMANIA": "EUROPE",
    "SAUDI ARABIA": "MIDDLE EAST", "VIETNAM": "ASIA", "RUSSIA": "EUROPE",
    "UNITED KINGDOM": "EUROPE", "UNITED STATES": "AMERICA",
}
SEGMENTS = ["AUTOMOBILE", "BUILDING", "FURNITURE", "MACHINERY", "HOUSEHOLD"]
TYPE_S1 = ["STANDARD", "SMALL", "MEDIUM", "LARGE", "ECONOMY", "PROMO"]
TYPE_S2 = ["ANODIZED", "BURNISHED", "PLATED", "POLISHED", "BRUSHED"]
TYPE_S3 = ["TIN", "NICKEL", "BRASS", "STEEL", "COPPER"]
CONTAINER_S1 = ["SM", "LG", "MED", "JUMBO", "WRAP"]
CONTAINER_S2 = ["CASE", "BOX", "BAG", "JAR", "PKG", "PACK", "CAN", "DRUM"]
SHIPMODES = ["REG AIR", "AIR", "RAIL", "SHIP", "TRUCK", "MAIL", "FOB"]
COLORS = (
    "almond antique aquamarine azure beige bisque black blanched blue blush brown burlywood "
    "burnished chartreuse chiffon chocolate coral cornflower cornsilk cream cyan dark deep dim "
    "dodger drab firebrick floral forest frosted gainsboro ghost goldenrod green grey honeydew "
    "hot indian ivory khaki lace lavender lawn lemon light lime linen magenta maroon medium "
    "metallic midnight mint misty moccasin navajo navy olive orange orchid pale papaya peach "
    "peru pink plum powder puff purple red rose rosy royal saddle salmon sandy seashell sienna "
    "sky slate smoke snow spring steel tan thistle tomato turquoise violet wheat white yellow"
).split()
Q13_WORD1 = ["special", "pending", "unusual", "express"]
Q13_WORD2 = ["packages", "requests", "accounts", "deposits"]


def _brand(r):
    return f"Brand#{r.randint(1, 5)}{r.randint(1, 5)}"


def _jan1(r):
    return f"{r.randint(1993, 1997)}-01-01"


def _month_start(r, first=(1993, 1), last=(1997, 10)):
    months = (last[0] - first[0]) * 12 + (last[1] - first[1])
    k = r.randint(0, months)
    y, m = divmod(first[1] - 1 + k, 12)
    return f"{first[0] + y}-{m + 1:02d}-01"


def _p1(r, sf):
    return {"delta": r.randint(60, 120)}


def _p2(r, sf):
    return {"size": r.randint(1, 50), "type": r.choice(TYPE_S3), "region": r.choice(REGIONS)}


def _p3(r, sf):
    return {"segment": r.choice(SEGMENTS), "date": str(dt.date(1995, 3, 1) + dt.timedelta(days=r.randint(0, 30)))}


def _p4(r, sf):
    return {"date": _month_start(r)}


def _p5(r, sf):
    return {"region": r.choice(REGIONS), "date": _jan1(r)}


def _p6(r, sf):
    return {"date": _jan1(r), "discount": f"0.0{r.randint(2, 9)}", "quantity": r.randint(24, 25)}


def _p7(r, sf):
    n1, n2 = r.sample(sorted(NATIONS), 2)
    return {"nation1": n1, "nation2": n2}


def _p8(r, sf):
    nation = r.choice(sorted(NATIONS))
    return {"nation": nation, "region": NATIONS[nation],
            "type": f"{r.choice(TYPE_S1)} {r.choice(TYPE_S2)} {r.choice(TYPE_S3)}"}


def _p9(r, sf):
    return {"color": r.choice(COLORS)}


def _p10(r, sf):
    return {"date": _month_start(r, (1993, 2), (1995, 1))}


def _p11(r, sf):
    return {"nation": r.choice(sorted(NATIONS)), "fraction": f"{0.0001 / sf:.10f}"}


def _p12(r, sf):
    m1, m2 = r.sample(SHIPMODES, 2)
    return {"shipmode1": m1, "shipmode2": m2, "date": _jan1(r)}


def _p13(r, sf):
    return {"word1": r.choice(Q13_WORD1), "word2": r.choice(Q13_WORD2)}


def _p14(r, sf):
    return {"date": _month_start(r, (1993, 1), (1997, 12))}


def _p15(r, sf):
    return {"date": _month_start(r)}


def _p16(r, sf):
    return {"brand": _brand(r), "type": f"{r.choice(TYPE_S1)} {r.choice(TYPE_S2)}",
            "sizes": ", ".join(map(str, r.sample(range(1, 51), 8)))}


def _p17(r, sf):
    return {"brand": _brand(r), "container": f"{r.choice(CONTAINER_S1)} {r.choice(CONTAINER_S2)}"}


def _p18(r, sf):
    return {"quantity": r.randint(312, 315)}


def _p19(r, sf):
    return {"brand1": _brand(r), "brand2": _brand(r), "brand3": _brand(r),
            "q1": r.randint(1, 10), "q2": r.randint(10, 20), "q3": r.randint(20, 30)}


def _p20(r, sf):
    return {"color": r.choice(COLORS), "date": _jan1(r), "nation": r.choice(sorted(NATIONS))}


def _p21(r, sf):
    return {"nation": r.choice(sorted(NATIONS))}


def _p22(r, sf):
    return {"codes": ", ".join(f"'{c}'" for c in r.sample(range(10, 35), 7))}


TEMPLATES = {
    "q01": (_p1, """
        SELECT l_returnflag, l_linestatus, sum(l_quantity) AS sum_qty, sum(l_extendedprice) AS sum_base_price,
               sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price,
               sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge,
               avg(l_quantity) AS avg_qty, avg(l_extendedprice) AS avg_price, avg(l_discount) AS avg_disc,
               count(*) AS count_order
        FROM lineitem
        WHERE l_shipdate <= DATE '1998-12-01' - INTERVAL '{delta}' DAY
        GROUP BY l_returnflag, l_linestatus
        ORDER BY l_returnflag, l_linestatus"""),
    "q02": (_p2, """
        SELECT s_acctbal, s_name, n_name, p_partkey, p_mfgr, s_address, s_phone, s_comment
        FROM part, supplier, partsupp, nation, region
        WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND p_size = {size} AND p_type LIKE '%{type}'
          AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey AND r_name = '{region}'
          AND ps_supplycost = (
              SELECT min(ps_supplycost) FROM partsupp, supplier, nation, region
              WHERE p_partkey = ps_partkey AND s_suppkey = ps_suppkey AND s_nationkey = n_nationkey
                AND n_regionkey = r_regionkey AND r_name = '{region}')
        ORDER BY s_acctbal DESC, n_name, s_name, p_partkey
        LIMIT 100"""),
    "q03": (_p3, """
        SELECT l_orderkey, sum(l_extendedprice * (1 - l_discount)) AS revenue, o_orderdate, o_shippriority
        FROM customer, orders, lineitem
        WHERE c_mktsegment = '{segment}' AND c_custkey = o_custkey AND l_orderkey = o_orderkey
          AND o_orderdate < DATE '{date}' AND l_shipdate > DATE '{date}'
        GROUP BY l_orderkey, o_orderdate, o_shippriority
        ORDER BY revenue DESC, o_orderdate, l_orderkey
        LIMIT 10"""),
    "q04": (_p4, """
        SELECT o_orderpriority, count(*) AS order_count
        FROM orders
        WHERE o_orderdate >= DATE '{date}' AND o_orderdate < DATE '{date}' + INTERVAL '3' MONTH
          AND EXISTS (SELECT * FROM lineitem WHERE l_orderkey = o_orderkey AND l_commitdate < l_receiptdate)
        GROUP BY o_orderpriority
        ORDER BY o_orderpriority"""),
    "q05": (_p5, """
        SELECT n_name, sum(l_extendedprice * (1 - l_discount)) AS revenue
        FROM customer, orders, lineitem, supplier, nation, region
        WHERE c_custkey = o_custkey AND l_orderkey = o_orderkey AND l_suppkey = s_suppkey
          AND c_nationkey = s_nationkey AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey
          AND r_name = '{region}' AND o_orderdate >= DATE '{date}'
          AND o_orderdate < DATE '{date}' + INTERVAL '1' YEAR
        GROUP BY n_name
        ORDER BY revenue DESC, n_name"""),
    "q06": (_p6, """
        SELECT sum(l_extendedprice * l_discount) AS revenue
        FROM lineitem
        WHERE l_shipdate >= DATE '{date}' AND l_shipdate < DATE '{date}' + INTERVAL '1' YEAR
          AND l_discount BETWEEN {discount} - 0.01 AND {discount} + 0.01 AND l_quantity < {quantity}"""),
    "q07": (_p7, """
        SELECT supp_nation, cust_nation, l_year, sum(volume) AS revenue
        FROM (
            SELECT n1.n_name AS supp_nation, n2.n_name AS cust_nation, extract(year FROM l_shipdate) AS l_year,
                   l_extendedprice * (1 - l_discount) AS volume
            FROM supplier, lineitem, orders, customer, nation n1, nation n2
            WHERE s_suppkey = l_suppkey AND o_orderkey = l_orderkey AND c_custkey = o_custkey
              AND s_nationkey = n1.n_nationkey AND c_nationkey = n2.n_nationkey
              AND ((n1.n_name = '{nation1}' AND n2.n_name = '{nation2}')
                   OR (n1.n_name = '{nation2}' AND n2.n_name = '{nation1}'))
              AND l_shipdate BETWEEN DATE '1995-01-01' AND DATE '1996-12-31') AS shipping
        GROUP BY supp_nation, cust_nation, l_year
        ORDER BY supp_nation, cust_nation, l_year"""),
    "q08": (_p8, """
        SELECT o_year, sum(CASE WHEN nation = '{nation}' THEN volume ELSE 0 END) / sum(volume) AS mkt_share
        FROM (
            SELECT extract(year FROM o_orderdate) AS o_year, l_extendedprice * (1 - l_discount) AS volume,
                   n2.n_name AS nation
            FROM part, supplier, lineitem, orders, customer, nation n1, nation n2, region
            WHERE p_partkey = l_partkey AND s_suppkey = l_suppkey AND l_orderkey = o_orderkey
              AND o_custkey = c_custkey AND c_nationkey = n1.n_nationkey AND n1.n_regionkey = r_regionkey
              AND r_name = '{region}' AND s_nationkey = n2.n_nationkey
              AND o_orderdate BETWEEN DATE '1995-01-01' AND DATE '1996-12-31' AND p_type = '{type}') AS all_nations
        GROUP BY o_year
        ORDER BY o_year"""),
    "q09": (_p9, """
        SELECT nation, o_year, sum(amount) AS sum_profit
        FROM (
            SELECT n_name AS nation, extract(year FROM o_orderdate) AS o_year,
                   l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount
            FROM part, supplier, lineitem, partsupp, orders, nation
            WHERE s_suppkey = l_suppkey AND ps_suppkey = l_suppkey AND ps_partkey = l_partkey
              AND p_partkey = l_partkey AND o_orderkey = l_orderkey AND s_nationkey = n_nationkey
              AND p_name LIKE '%{color}%') AS profit
        GROUP BY nation, o_year
        ORDER BY nation, o_year DESC"""),
    "q10": (_p10, """
        SELECT c_custkey, c_name, sum(l_extendedprice * (1 - l_discount)) AS revenue, c_acctbal, n_name,
               c_address, c_phone, c_comment
        FROM customer, orders, lineitem, nation
        WHERE c_custkey = o_custkey AND l_orderkey = o_orderkey AND o_orderdate >= DATE '{date}'
          AND o_orderdate < DATE '{date}' + INTERVAL '3' MONTH AND l_returnflag = 'R'
          AND c_nationkey = n_nationkey
        GROUP BY c_custkey, c_name, c_acctbal, c_phone, n_name, c_address, c_comment
        ORDER BY revenue DESC, c_custkey
        LIMIT 20"""),
    "q11": (_p11, """
        SELECT ps_partkey, sum(ps_supplycost * ps_availqty) AS value
        FROM partsupp, supplier, nation
        WHERE ps_suppkey = s_suppkey AND s_nationkey = n_nationkey AND n_name = '{nation}'
        GROUP BY ps_partkey
        HAVING sum(ps_supplycost * ps_availqty) > (
            SELECT sum(ps_supplycost * ps_availqty) * {fraction}
            FROM partsupp, supplier, nation
            WHERE ps_suppkey = s_suppkey AND s_nationkey = n_nationkey AND n_name = '{nation}')
        ORDER BY value DESC, ps_partkey"""),
    "q12": (_p12, """
        SELECT l_shipmode,
               sum(CASE WHEN o_orderpriority = '1-URGENT' OR o_orderpriority = '2-HIGH' THEN 1 ELSE 0 END) AS high_line_count,
               sum(CASE WHEN o_orderpriority <> '1-URGENT' AND o_orderpriority <> '2-HIGH' THEN 1 ELSE 0 END) AS low_line_count
        FROM orders, lineitem
        WHERE o_orderkey = l_orderkey AND l_shipmode IN ('{shipmode1}', '{shipmode2}')
          AND l_commitdate < l_receiptdate AND l_shipdate < l_commitdate
          AND l_receiptdate >= DATE '{date}' AND l_receiptdate < DATE '{date}' + INTERVAL '1' YEAR
        GROUP BY l_shipmode
        ORDER BY l_shipmode"""),
    "q13": (_p13, """
        SELECT c_count, count(*) AS custdist
        FROM (
            SELECT c_custkey, count(o_orderkey)
            FROM customer LEFT OUTER JOIN orders
              ON c_custkey = o_custkey AND o_comment NOT LIKE '%{word1}%{word2}%'
            GROUP BY c_custkey) AS c_orders (c_custkey, c_count)
        GROUP BY c_count
        ORDER BY custdist DESC, c_count DESC"""),
    "q14": (_p14, """
        SELECT 100.00 * sum(CASE WHEN p_type LIKE 'PROMO%' THEN l_extendedprice * (1 - l_discount) ELSE 0 END)
               / sum(l_extendedprice * (1 - l_discount)) AS promo_revenue
        FROM lineitem, part
        WHERE l_partkey = p_partkey AND l_shipdate >= DATE '{date}'
          AND l_shipdate < DATE '{date}' + INTERVAL '1' MONTH"""),
    "q15": (_p15, """
        WITH revenue AS (
            SELECT l_suppkey AS supplier_no, sum(l_extendedprice * (1 - l_discount)) AS total_revenue
            FROM lineitem
            WHERE l_shipdate >= DATE '{date}' AND l_shipdate < DATE '{date}' + INTERVAL '3' MONTH
            GROUP BY l_suppkey)
        SELECT s_suppkey, s_name, s_address, s_phone, total_revenue
        FROM supplier, revenue
        WHERE s_suppkey = supplier_no AND total_revenue = (SELECT max(total_revenue) FROM revenue)
        ORDER BY s_suppkey"""),
    "q16": (_p16, """
        SELECT p_brand, p_type, p_size, count(DISTINCT ps_suppkey) AS supplier_cnt
        FROM partsupp, part
        WHERE p_partkey = ps_partkey AND p_brand <> '{brand}' AND p_type NOT LIKE '{type}%'
          AND p_size IN ({sizes})
          AND ps_suppkey NOT IN (SELECT s_suppkey FROM supplier WHERE s_comment LIKE '%Customer%Complaints%')
        GROUP BY p_brand, p_type, p_size
        ORDER BY supplier_cnt DESC, p_brand, p_type, p_size"""),
    "q17": (_p17, """
        SELECT sum(l_extendedprice) / 7.0 AS avg_yearly
        FROM lineitem, part
        WHERE p_partkey = l_partkey AND p_brand = '{brand}' AND p_container = '{container}'
          AND l_quantity < (SELECT 0.2 * avg(l_quantity) FROM lineitem WHERE l_partkey = p_partkey)"""),
    "q18": (_p18, """
        SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS sum_qty
        FROM customer, orders, lineitem
        WHERE o_orderkey IN (SELECT l_orderkey FROM lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > {quantity})
          AND c_custkey = o_custkey AND o_orderkey = l_orderkey
        GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice
        ORDER BY o_totalprice DESC, o_orderdate, o_orderkey
        LIMIT 100"""),
    "q19": (_p19, """
        SELECT sum(l_extendedprice * (1 - l_discount)) AS revenue
        FROM lineitem, part
        WHERE (p_partkey = l_partkey AND p_brand = '{brand1}'
               AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG')
               AND l_quantity >= {q1} AND l_quantity <= {q1} + 10 AND p_size BETWEEN 1 AND 5
               AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')
           OR (p_partkey = l_partkey AND p_brand = '{brand2}'
               AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK')
               AND l_quantity >= {q2} AND l_quantity <= {q2} + 10 AND p_size BETWEEN 1 AND 10
               AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')
           OR (p_partkey = l_partkey AND p_brand = '{brand3}'
               AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG')
               AND l_quantity >= {q3} AND l_quantity <= {q3} + 10 AND p_size BETWEEN 1 AND 15
               AND l_shipmode IN ('AIR', 'AIR REG') AND l_shipinstruct = 'DELIVER IN PERSON')"""),
    "q20": (_p20, """
        SELECT s_name, s_address
        FROM supplier, nation
        WHERE s_suppkey IN (
                SELECT ps_suppkey FROM partsupp
                WHERE ps_partkey IN (SELECT p_partkey FROM part WHERE p_name LIKE '{color}%')
                  AND ps_availqty > (
                      SELECT 0.5 * sum(l_quantity) FROM lineitem
                      WHERE l_partkey = ps_partkey AND l_suppkey = ps_suppkey
                        AND l_shipdate >= DATE '{date}' AND l_shipdate < DATE '{date}' + INTERVAL '1' YEAR))
          AND s_nationkey = n_nationkey AND n_name = '{nation}'
        ORDER BY s_name"""),
    "q21": (_p21, """
        SELECT s_name, count(*) AS numwait
        FROM supplier, lineitem l1, orders, nation
        WHERE s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey AND o_orderstatus = 'F'
          AND l1.l_receiptdate > l1.l_commitdate
          AND EXISTS (SELECT * FROM lineitem l2
                      WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey)
          AND NOT EXISTS (SELECT * FROM lineitem l3
                          WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey
                            AND l3.l_receiptdate > l3.l_commitdate)
          AND s_nationkey = n_nationkey AND n_name = '{nation}'
        GROUP BY s_name
        ORDER BY numwait DESC, s_name
        LIMIT 100"""),
    "q22": (_p22, """
        SELECT cntrycode, count(*) AS numcust, sum(c_acctbal) AS totacctbal
        FROM (
            SELECT substring(c_phone FROM 1 FOR 2) AS cntrycode, c_acctbal
            FROM customer
            WHERE substring(c_phone FROM 1 FOR 2) IN ({codes})
              AND c_acctbal > (SELECT avg(c_acctbal) FROM customer
                               WHERE c_acctbal > 0.00 AND substring(c_phone FROM 1 FOR 2) IN ({codes}))
              AND NOT EXISTS (SELECT * FROM orders WHERE o_custkey = c_custkey)) AS custsale
        GROUP BY cntrycode
        ORDER BY cntrycode"""),
}


def instantiate(template: str, rng, scale_factor: float) -> tuple[str, tuple]:
    param_fn, sql = TEMPLATES[template]
    params = param_fn(rng, scale_factor)
    text = re.sub(r"\s+", " ", sql.format(**params)).strip()
    return text, tuple(sorted(params.items()))


def datagen_sql(scale_factor: float) -> str:
    """Runs in the *baseline* binary, which has the tpch extension linked in."""
    return f"CALL dbgen(sf = {scale_factor});"


def audit_patterns() -> list[str]:
    """Regexes that have no business appearing in engine source: schema names and query literals.

    Short common words (part, orders, region, nation) are left out on purpose; the column-name
    pattern and the distinctive table names catch workload-specific code without false alarms.
    """
    return [
        r"\b[lopcsnr]_[a-z]+key\b", r"\bps_[a-z]+\b",
        r"\bl_(shipdate|commitdate|receiptdate|extendedprice|discount|quantity|returnflag|linestatus|shipmode|shipinstruct|tax)\b",
        r"\bo_(orderdate|orderpriority|orderstatus|totalprice|comment|shippriority)\b",
        r"\b(p_brand|p_container|p_mfgr|p_retailprice|c_mktsegment|c_acctbal|s_acctbal|n_regionkey)\b",
        r"\blineitem\b", r"\bpartsupp\b", r"(?i)\btpc-?h\b", r"(?i)\bdbgen\b",
        r"Brand#", r"Customer%Complaints", r"DELIVER IN PERSON", r"1-URGENT", r"2-HIGH", r"PROMO%",
    ]
