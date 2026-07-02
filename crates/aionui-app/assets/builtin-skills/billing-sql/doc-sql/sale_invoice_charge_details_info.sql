SELECT
    T.CUST_ORDER_ID,
    T.ACC_NBR,
    T.ACCT_ID,
    T.CHARGE,
    T.DISCOUNT_CHARGE,
    T.FEE_ITEM,
    T.PAYMENT_TIME,
    T.PAYMENT_DATE,
    T.AGREEMENT_PERIOD,
    T.TAX_CHARGE,
    T.Rounding_amount,
    T.TAX_RATE,
    T.OFFER_NAME,
     CASE
        WHEN T.GOODS_ORDER_ID IS NOT NULL AND
             T.CHARGE = MAX(T.CHARGE) OVER (PARTITION BY T.CUST_ORDER_ID, T.ACC_NBR, T.GOODS_ORDER_ID)
        THEN LISTAGG(DISTINCT T.MODEL_NAME, CHR(10)) WITHIN GROUP (ORDER BY
                 CASE WHEN T.MODEL_NAME LIKE '%Adapter%' THEN 2 ELSE 1 END,
                 T.MODEL_NAME
             ) OVER (PARTITION BY T.CUST_ORDER_ID)
        ELSE NULL
    END AS MODEL_NAME,
    T.GOODS_ORDER_ID
FROM
    (SELECT
        B.CUST_ORDER_ID,
        B.ACC_NBR,
        B.ACCT_ID,
        B.CHARGE AS CHARGE,
        B.DISCOUNT_CHARGE AS DISCOUNT_CHARGE,
        B.FEE_ITEM,
        B.PAYMENT_TIME,
        B.PAYMENT_DATE,
        B.AGREEMENT_PERIOD,
        T.CHARGE AS TAX_CHARGE,
        CASE WHEN ROW_NUMBER() OVER (PARTITION BY B.CUST_ORDER_ID ORDER BY B.DEDUCT_SEQ) = 1
             THEN NVL(R.ROUNDING_AMOUNT, 0)
             ELSE 0
        END AS ROUNDING_AMOUNT,
        B.TAX_RATE,
        B.OFFER_NAME,
        M.GOODS_ORDER_ID,
        M.MODEL_NAME
    FROM (
        -- Main fee records
        SELECT
            D.CUST_ORDER_ID,
            B.DEDUCT_SEQ,
            B.PRICE_ID,
            D.ACC_NBR,
            D.ACCT_ID,
            B.CHARGE,
            B.DISCOUNT_CHARGE,
            F.ACCT_ITEM_TYPE_NAME AS FEE_ITEM,
            TO_CHAR(B.State_Date, 'HH:MIam') AS PAYMENT_TIME,
            TO_CHAR(B.State_Date, 'DD-Mon-YYYY') AS PAYMENT_DATE,
            CASE
                WHEN M.agreement_period <> 0 THEN
                     TO_CHAR(SA.EFF_DATE, 'DD Mon YYYY') || ' – ' || TO_CHAR(SA.EXP_DATE, 'DD Mon YYYY')
                ELSE
                     NULL
            END AS AGREEMENT_PERIOD,
            G.TAX_RATE,
            AG.AGREEMENT_SHORT_NAME AS OFFER_NAME,
            F.ACCT_ITEM_TYPE_ID,
            F.ACCT_ITEM_TYPE_CODE,
            EP.EVENT_PAYMENT_ID
        FROM RE_CC_INST A, EVENT_CHARGE B, RE_SUBS_ORDER_INST C, CRM.ORDER_ITEM D, ACCT_ITEM_TYPE F, EVENT_CHARGE_EXT H, GST_TYPE_TAX_RATE G, OFFER J, GST_TYPE K,CRM.AGREEMENT_ORDER M,AGREEMENT AG,
        EVENT_PAYMENT EP, SUBS_AGREEMENT_INST SA
        WHERE A.EVENT_INST_ID = B.EVENT_INST_ID
        AND M.SUBS_AGREEMENT_INST_ID=SA.AGREEMENT_INST_ID
        AND A.EVENT_INST_ID = C.EVENT_INST_ID
        AND D.ORDER_ITEM_ID = C.ORDER_ITEM_ID
        AND F.ACCT_ITEM_TYPE_ID = B.ACCT_ITEM_TYPE_ID
        AND B.BILLING_CYCLE_ID IS NOT NULL
        AND B.E_INVOICE_NBR = :E_INVOICE_NBR
        AND H.EVENT_INST_ID = B.EVENT_INST_ID
        AND H.PRICE_ID = B.PRICE_ID
        AND D.SUBS_PLAN_ID = J.OFFER_iD
        AND C.CUST_ORDER_ID = D.CUST_ORDER_ID
        AND H.SEQ = B.SEQ
        AND F.GST_TYPE = K.GST_TYPE
        AND F.GST_TYPE <> 'Z'
        AND H.DEDUCT_SEQ = B.DEDUCT_SEQ
        AND H.IS_TAX IS NULL
        AND F.GST_TYPE = G.GST_TYPE
        AND D.ORDER_ITEM_ID=M.ORDER_ITEM_ID
        AND M.AGREEMENT_ID = AG.AGREEMENT_ID
        AND C.EVENT_PAYMENT_ID=EP.EVENT_PAYMENT_ID
        AND D.SUBS_EVENT_ID=1
    ) B
    -- Tax records
    LEFT JOIN (
        SELECT
            D.CUST_ORDER_ID,
            B.DEDUCT_SEQ,
            B.PRICE_ID,
            B.CHARGE,
            D.ACC_NBR
        FROM RE_CC_INST A, EVENT_CHARGE B, RE_SUBS_ORDER_INST C, CRM.ORDER_ITEM D, EVENT_CHARGE_EXT H,EVENT_PAYMENT EP
        WHERE A.EVENT_INST_ID = B.EVENT_INST_ID
        AND A.EVENT_INST_ID = C.EVENT_INST_ID
        AND D.ORDER_ITEM_ID = C.ORDER_ITEM_ID
        AND B.BILLING_CYCLE_ID IS NOT NULL
        AND B.E_INVOICE_NBR = :E_INVOICE_NBR
        AND H.EVENT_INST_ID = B.EVENT_INST_ID
        AND H.PRICE_ID = B.PRICE_ID
        AND H.SEQ = B.SEQ
        AND C.EVENT_PAYMENT_ID=EP.EVENT_PAYMENT_ID
        AND C.CUST_ORDER_ID = D.CUST_ORDER_ID
        AND H.DEDUCT_SEQ = B.DEDUCT_SEQ
        AND H.IS_TAX = 'Y'
        AND D.SUBS_EVENT_ID=1
    ) T ON T.PRICE_ID = B.PRICE_ID
        AND T.DEDUCT_SEQ <> B.DEDUCT_SEQ
        AND T.ACC_NBR = B.ACC_NBR
        AND T.CUST_ORDER_ID = B.CUST_ORDER_ID
    -- Rounding amount
    LEFT JOIN (
        SELECT
            D.CUST_ORDER_ID,
            MAX(B.CHARGE) AS ROUNDING_AMOUNT
        FROM RE_CC_INST A, EVENT_CHARGE B, RE_SUBS_ORDER_INST C, CRM.ORDER_ITEM D, ACCT_ITEM_TYPE F
        WHERE A.EVENT_INST_ID = B.EVENT_INST_ID
        AND A.EVENT_INST_ID = C.EVENT_INST_ID
        AND D.ORDER_ITEM_ID = C.ORDER_ITEM_ID
        AND C.CUST_ORDER_ID = D.CUST_ORDER_ID
        AND D.SUBS_EVENT_ID=1
        AND F.ACCT_ITEM_TYPE_ID = B.ACCT_ITEM_TYPE_ID
        AND B.BILLING_CYCLE_ID IS NOT NULL
        AND B.E_INVOICE_NBR = :E_INVOICE_NBR
        AND F.ACCT_ITEM_TYPE_CODE IN ('ROUNDING')
        GROUP BY D.CUST_ORDER_ID
    ) R ON R.CUST_ORDER_ID = B.CUST_ORDER_ID
    LEFT JOIN (
        ---- GOODS Info - 修改品牌拼接逻辑和显示顺序
        SELECT
            CUST_ORDER_ID,
            GOODS_ORDER_ID,
            ACC_NBR,
            MODEL_NAME
        FROM (
            SELECT DISTINCT
                D.CUST_ORDER_ID,
                E.GOODS_ORDER_ID,
                D.ACC_NBR,
                CASE
                    WHEN H.MODEL_NAME LIKE '%Adapter%' THEN
                        -- Adapter类型：品牌 + 型号 + 属性值
                        CASE WHEN I_ADAPTER.VALUE IS NOT NULL
                             THEN BR.BRAND_NAME || ' ' || H.MODEL_NAME || ',' || I_ADAPTER.VALUE
                             ELSE BR.BRAND_NAME || ' ' || H.MODEL_NAME
                        END
                    ELSE
                        -- 非Adapter类型：型号 + 品牌 + 属性值
                        CASE WHEN I_PHONE.VALUE IS NOT NULL
                             THEN BR.BRAND_NAME || ' ' || H.MODEL_NAME || ',' || I_PHONE.VALUE
                             ELSE BR.BRAND_NAME || ' ' || H.MODEL_NAME
                        END
                END AS MODEL_NAME,
                -- 添加排序字段，Adapter类型排在后面
                CASE WHEN H.MODEL_NAME LIKE '%Adapter%' THEN 2 ELSE 1 END AS SORT_ORDER
            FROM
                RE_CC_INST A
                JOIN EVENT_CHARGE B ON A.EVENT_INST_ID = B.EVENT_INST_ID
                JOIN RE_SUBS_ORDER_INST C ON A.EVENT_INST_ID = C.EVENT_INST_ID
                JOIN CRM.ORDER_ITEM D ON D.ORDER_ITEM_ID = C.ORDER_ITEM_ID AND D.CUST_ORDER_ID = C.CUST_ORDER_ID
                JOIN ACCT_ITEM_TYPE F ON F.ACCT_ITEM_TYPE_ID = B.ACCT_ITEM_TYPE_ID
                JOIN CRM.GOODS_ORDER E ON D.ORDER_ITEM_ID = E.ORDER_ITEM_ID
                JOIN CRM.GM_MODEL H ON H.MODEL_ID = E.MODEL_ID
                JOIN CRM.GM_BRAND BR ON H.BRAND_ID=BR.BRAND_ID
                AND BR.BRAND_CODE NOT IN ('YES','Others')
                JOIN CRM.AGREEMENT_ORDER M ON D.ORDER_ITEM_ID = M.ORDER_ITEM_ID
                JOIN AGREEMENT AG ON M.AGREEMENT_ID = AG.AGREEMENT_ID
                AND AG.AGREEMENT_TYPE_ID='4'
                -- 对于Adapter类型，取属性907129
                LEFT JOIN CRM.GOODS_ORDER_ATTR I_ADAPTER ON E.GOODS_ORDER_ID = I_ADAPTER.GOODS_ORDER_ID
                    AND I_ADAPTER.ATTR_ID = 907129
                    AND H.MODEL_NAME LIKE '%Adapter%'
                -- 对于非Adapter类型，取属性2725
                LEFT JOIN CRM.GOODS_ORDER_ATTR I_PHONE ON E.GOODS_ORDER_ID = I_PHONE.GOODS_ORDER_ID
                    AND I_PHONE.ATTR_ID = 2725
                    AND H.MODEL_NAME NOT LIKE '%Adapter%'
            WHERE
                B.BILLING_CYCLE_ID IS NOT NULL
                AND B.E_INVOICE_NBR = :E_INVOICE_NBR
                AND D.SUBS_EVENT_ID = 1
        )
    ) M ON M.CUST_ORDER_ID = B.CUST_ORDER_ID AND M.ACC_NBR = B.ACC_NBR

    UNION ALL

    --tax部分
    SELECT
        P.CUST_ORDER_ID,
        P.ACC_NBR,
        P.ACCT_ID,
        P.CHARGE AS CHARGE,
        P.DISCOUNT_CHARGE AS DISCOUNT_CHARGE,
        P.FEE_ITEM,
        P.PAYMENT_TIME,
        P.PAYMENT_DATE,
        P.AGREEMENT_PERIOD,
        P.TAX_CHARGE AS TAX_CHARGE,
        P.ROUNDING_AMOUNT,
        P.TAX_RATE,
        P.OFFER_NAME,
        M.GOODS_ORDER_ID,
        M.MODEL_NAME
    FROM (
        SELECT
            D.CUST_ORDER_ID,
            D.ACC_NBR,
            D.ACCT_ID,
            B.CHARGE AS CHARGE,
            B.DISCOUNT_CHARGE AS DISCOUNT_CHARGE,
            F.ACCT_ITEM_TYPE_NAME AS FEE_ITEM,
            TO_CHAR(B.State_Date, 'HH:MIam') AS PAYMENT_TIME,
            TO_CHAR(B.State_Date, 'DD-Mon-YYYY') AS PAYMENT_DATE,
            CASE
                WHEN M.agreement_period <> 0 THEN
                     TO_CHAR(SA.EFF_DATE, 'DD Mon YYYY') || ' – ' || TO_CHAR(SA.EXP_DATE, 'DD Mon YYYY')
                ELSE
                     NULL
            END AS AGREEMENT_PERIOD,
            0 AS TAX_CHARGE,
            0 AS ROUNDING_AMOUNT,
            J.TAX_RATE,
            AG.AGREEMENT_SHORT_NAME AS OFFER_NAME
        FROM RE_CC_INST A, EVENT_CHARGE B, RE_SUBS_ORDER_INST C, CRM.ORDER_ITEM D, ACCT_ITEM_TYPE F,GST_TYPE H,GST_TYPE_TAX_RATE J,OFFER K,CRM.AGREEMENT_ORDER M,AGREEMENT AG,
        SUBS_AGREEMENT_INST SA
        WHERE A.EVENT_INST_ID = B.EVENT_INST_ID
        AND A.EVENT_INST_ID = C.EVENT_INST_ID
        AND M.SUBS_AGREEMENT_INST_ID=SA.AGREEMENT_INST_ID
        AND D.ORDER_ITEM_ID = C.ORDER_ITEM_ID
        AND F.GST_TYPE = H.GST_TYPE
        AND D.SUBS_PLAN_ID=K.OFFER_ID
        AND D.SUBS_EVENT_ID=1
        AND D.CUST_ORDER_ID = C.CUST_ORDER_ID
        AND F.ACCT_ITEM_TYPE_ID = B.ACCT_ITEM_TYPE_ID
        AND B.BILLING_CYCLE_ID IS NOT NULL
        AND B.E_INVOICE_NBR = :E_INVOICE_NBR
        AND H.GST_TYPE = 'Z'
        AND D.ORDER_ITEM_ID=M.ORDER_ITEM_ID
        AND M.AGREEMENT_ID = AG.AGREEMENT_ID
        AND H.GST_TYPE=J.GST_TYPE
        AND F.ACCT_ITEM_TYPE_CODE not in ('ZRL','ROUNDING')
    ) P
    LEFT JOIN (
        ---- GOODS Info - 同样修改品牌拼接逻辑和显示顺序
        SELECT
            CUST_ORDER_ID,
            GOODS_ORDER_ID,
            ACC_NBR,
            MODEL_NAME
        FROM (
            SELECT DISTINCT
                D.CUST_ORDER_ID,
                E.GOODS_ORDER_ID,
                D.ACC_NBR,
                CASE
                    WHEN H.MODEL_NAME LIKE '%Adapter%' THEN
                        -- Adapter类型：品牌 + 型号 + 属性值
                        CASE WHEN I_ADAPTER.VALUE IS NOT NULL
                             THEN BR.BRAND_NAME || ' ' || H.MODEL_NAME || ',' || I_ADAPTER.VALUE
                             ELSE BR.BRAND_NAME || ' ' || H.MODEL_NAME
                        END
                    ELSE
                        -- 非Adapter类型：型号 + 品牌 + 属性值
                       CASE WHEN I_PHONE.VALUE IS NOT NULL
                             THEN BR.BRAND_NAME || ' ' || H.MODEL_NAME || ',' || I_PHONE.VALUE
                             ELSE BR.BRAND_NAME || ' ' || H.MODEL_NAME
                        END
                END AS MODEL_NAME,
                -- 添加排序字段，Adapter类型排在后面
                CASE WHEN H.MODEL_NAME LIKE '%Adapter%' THEN 2 ELSE 1 END AS SORT_ORDER
            FROM
                RE_CC_INST A
                JOIN EVENT_CHARGE B ON A.EVENT_INST_ID = B.EVENT_INST_ID
                JOIN RE_SUBS_ORDER_INST C ON A.EVENT_INST_ID = C.EVENT_INST_ID
                JOIN CRM.ORDER_ITEM D ON D.ORDER_ITEM_ID = C.ORDER_ITEM_ID AND D.CUST_ORDER_ID = C.CUST_ORDER_ID
                JOIN ACCT_ITEM_TYPE F ON F.ACCT_ITEM_TYPE_ID = B.ACCT_ITEM_TYPE_ID
                JOIN CRM.GOODS_ORDER E ON D.ORDER_ITEM_ID = E.ORDER_ITEM_ID
                JOIN CRM.GM_MODEL H ON H.MODEL_ID = E.MODEL_ID
                JOIN CRM.GM_BRAND BR ON H.BRAND_ID=BR.BRAND_ID
                JOIN CRM.AGREEMENT_ORDER M ON D.ORDER_ITEM_ID = M.ORDER_ITEM_ID
                JOIN AGREEMENT AG ON M.AGREEMENT_ID = AG.AGREEMENT_ID
                AND AG.AGREEMENT_TYPE_ID='4'
                AND BR.BRAND_CODE NOT IN ('YES','Others')
                -- 对于Adapter类型，取属性907129
                LEFT JOIN CRM.GOODS_ORDER_ATTR I_ADAPTER ON E.GOODS_ORDER_ID = I_ADAPTER.GOODS_ORDER_ID
                    AND I_ADAPTER.ATTR_ID = 907129
                    AND H.MODEL_NAME LIKE '%Adapter%'
                -- 对于非Adapter类型，取属性2725
                LEFT JOIN CRM.GOODS_ORDER_ATTR I_PHONE ON E.GOODS_ORDER_ID = I_PHONE.GOODS_ORDER_ID
                    AND I_PHONE.ATTR_ID = 2725
                    AND H.MODEL_NAME NOT LIKE '%Adapter%'
            WHERE
                B.BILLING_CYCLE_ID IS NOT NULL
                AND D.SUBS_EVENT_ID = 1
        )
    ) M ON M.CUST_ORDER_ID = P.CUST_ORDER_ID AND M.ACC_NBR = P.ACC_NBR

    UNION ALL

    SELECT
        D.CUST_ORDER_ID,
        D.ACC_NBR,
        D.ACCT_ID,
        A.CHARGE*-1,
        0 AS DISCOUNT_CHARGE,
        DT.NAME AS FEE_ITEM,
        TO_CHAR(A.State_Date, 'HH:MIam') AS PAYMENT_TIME,
        TO_CHAR(A.State_Date, 'DD-Mon-YYYY') AS PAYMENT_DATE,
        NULL AS AGREEMENT_PERIOD,
        0 AS TAX_CHARGE,
        0 AS ROUNDING_AMOUNT,
        0 AS TAX_RATE,
        AG.AGREEMENT_SHORT_NAME AS OFFER_NAME,
        NULL AS MODEL_NAME,
        NULL AS GOODS_ORDER_ID
    FROM deposit_charge A
    JOIN RE_SUBS_ORDER_INST B ON A.event_inst_id = B.event_inst_id
    JOIN DEPOSIT_TYPE DT ON DT.DEPOSIT_TYPE_ID=A.DEPOSIT_TYPE_ID
    JOIN event_payment C ON B.event_payment_Id = C.event_payment_Id
    JOIN CRM.ORDER_ITEM D ON B.ORDER_ITEM_ID = D.ORDER_ITEM_ID
    JOIN ACCT_ITEM_TYPE E ON A.ACCT_ITEM_TYPE_ID = E.ACCT_ITEM_TYPE_ID
    JOIN CRM.AGREEMENT_ORDER M ON D.ORDER_ITEM_ID = M.ORDER_ITEM_ID
    JOIN AGREEMENT AG ON M.AGREEMENT_ID = AG.AGREEMENT_ID
    JOIN INSTANT_PAYMENT IP ON IP.EVENT_PAYMENT_ID=B.EVENT_PAYMENT_ID
    WHERE  IP.E_INVOICE_NBR = :E_INVOICE_NBR
      AND D.SUBS_EVENT_ID = 1
      AND A.CHARGE<0
) T
ORDER BY T.CUST_ORDER_ID, T.ACC_NBR, T.CHARGE
