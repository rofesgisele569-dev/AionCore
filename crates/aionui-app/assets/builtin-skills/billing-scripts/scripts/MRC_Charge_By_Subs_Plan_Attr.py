def main(r):
    subsId = r.event.GetAttrEx(201).AsInteger()
    # Dictionary for tiered subscription plans, format: subs_plan_id: {'n_month_after': n months, 'tiered_mrc': tiered mrc}
    tieredSubsPlan = {12164:{'n_month_after': 37, 'tiered_mrc': 178},
                      12165:{'n_month_after': 37, 'tiered_mrc': 178},
                      12166:{'n_month_after': 37, 'tiered_mrc': 178}}
    firstCycleFreePlanList = [12162,12075]    # first regular mrc is 0
    currentTime = r.event.GetAttrEx(EVENT_BEGIN_TIME).AsInteger()
    cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
    cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
    cycleDays = diffdays(cycleEndTime,cycleBeginTime)
    subsPlanId = r.event.GetAttrEx(112).AsInteger()
    print("****subsPlanId****", subsPlanId)
    print("****cycleBeginTime****", cycleBeginTime)
    print("****cycleEndTime****", cycleEndTime)
    print("****cycleDays****", cycleDays)    
    pricePlanId = r.event.GetAttrEx(897).AsInteger()
    print("****pricePlanId****", pricePlanId)
    subsPlanInst = r.event.GetSubsUppInstEffExpTime(pricePlanId,'A')
    print("****subsPlanInst****", subsPlanInst)
    # zentao: 5056, 5058, for some agreement plan, no need to charge prorate mrc for new connection or plan conversion
    isProrateFree = int(r.event.GetAttrEx(2013).AsInteger() or -1)
    print("****isProrateFree****", isProrateFree)
    if subsPlanInst < 0:
        billingCycleOffset = -1
    else:       
        subsPlanEffDate = r.event.GetAttrEx(606).AsInteger()
        print("****subsPlanEffDate****", subsPlanEffDate)
        billingCycleOffset = r.event.GetBillingCycleOffsetIdFromCycleRefDate(subsId, currentTime, subsPlanEffDate)
    print("****billingCycleOffset****", billingCycleOffset)
    prodSpecId = int(r.event.GetAttrEx(15).AsInteger() or 0)
    prodState = r.event.GetIndependProdState()
    print("****prodState****", prodState)
    if prodSpecId == 0:
        prodSpecId = r.event.GetIndepProdSpecId()
    print("****prodSpecId****", prodSpecId)
    # get mrc, if there's customized overwritten mrc, then use it, otherwise use MCR attribute on subs plan
    overWrittenMRC  = float(r.event.GetPricePlanAttrValue("EXP_OVERWRITTEN_MRC") or '-1')
    print("****MigratedOverWrittenMRC****", overWrittenMRC)
    if overWrittenMRC == -1:
        overWrittenMRC = float(r.event.GetProdAttrValueByAttrCode('EXP_OVERWRITTEN_MRC',subsId) or '-1')
    print("****overWrittenMRC****", overWrittenMRC)
    subsPlanMRC  = float(r.event.GetPricePlanAttrValueBySubsPlanId('EXP_HNCNC_RENTAL_FEE',currentTime,subsPlanId,prodSpecId) or '0')
    print("****subsId****", subsId)
    print("****subsPlanMRC****", subsPlanMRC)
    if overWrittenMRC != -1:
        mrcCharge = overWrittenMRC
    else:
        mrcCharge = subsPlanMRC
    # for tiered mrc plan, use tiered mrc, do not use overWrittenMRC
    # for tiered mrc plan, there's no prorate mrc for new connection, and no mrc for the first bill-run
    if subsPlanId in tieredSubsPlan:
        planDetails = tieredSubsPlan[subsPlanId]
        nMonthAfter = planDetails['n_month_after']
        tieredMrc = planDetails['tiered_mrc']
        if billingCycleOffset >= nMonthAfter:
            mrcCharge = tieredMrc
    if subsPlanId in firstCycleFreePlanList and billingCycleOffset > 0 and billingCycleOffset <= 1:
        mrcCharge = 0
        print("****30DaysFreeMRC****", mrcCharge)
    mrcCharge = mrcCharge * 10000
    r.event.SetAttr(REC_MUST_BENFIT_FLAG,1)
    # get recurring deal mode, 0 - Offline Recurring Rate, 1 - Online Recurring Refund/Prorate, 2 - Mock
    dealMode = int(r.event.GetAttrEx(959).AsInteger() or 0)
    if dealMode == 0:
        print("****OfflineRecurringMode****", dealMode)
        agreementEffDate = int(r.event.GetAttrEx(2002).AsInteger() or -1)
        agreementExpDate = int(r.event.GetAttrEx(2003).AsInteger() or -1)
        print("****agreementEffDate****", agreementEffDate)
        print("****agreementExpDate****", agreementExpDate)
        print("****currentTime****", currentTime)
        # if state is TWB and without valid agreement, then no MRC
        # if state is TWB and with valid agreement, then charge full MRC and ignore online refund/prorate message
        if prodState == 'E':
            if ((currentTime < agreementEffDate) or (currentTime > agreementExpDate) or (agreementEffDate == agreementExpDate)):
                print("****NoAgreement****")
                mrcCharge = 0
            elif cycleBeginTime < agreementExpDate < cycleEndTime:
                print("****AgreementExpireInCurrentBillingCycle****")
                chargeDays = diffdays(agreementExpDate,cycleBeginTime)
                print("****chargeDays****",chargeDays)
                mrcCharge = round(1.0 * mrcCharge * chargeDays / cycleDays)
                r.event.SetAttr(862,cycleBeginTime)
                r.event.SetAttr(863,agreementExpDate)
        print("****OfflineRecurringModeMRC****", mrcCharge)
        r.event.SetAttrList(42,int(mrcCharge))
        r.event.SetAttr(REC_MUST_BENFIT_FLAG,1)
        r.SetResult(mrcCharge)
    elif dealMode == 2:
        print("****PreRealBillingRecurringMode****", dealMode)        
        processServiceType = int(r.event.GetAttrEx(PROCESS_SERVICE_TYPE).AsInteger() or 1)
        print("****processServiceType****", processServiceType)        
        immediateTime = StringToTime(r.event.GetAttrEx(IMMEDIATE_INVOICING_CUTOFF_DATE).AsString())        
        dealBillingCycleId = r.event.GetBillingCycleId(subsId, currentTime)
        immBillingCycleId = r.event.GetBillingCycleId(subsId, immediateTime)
        print("****PreRealBillingRecurringModeFullMRC****", mrcCharge)
        print("****cycleBeginTime****", cycleBeginTime)
        print("****cycleEndTime****", cycleEndTime)        
        print("****currentTime****", currentTime)
        print("****immediateTime****", immediateTime)
        print("****dealBillingCycleId****", dealBillingCycleId )
        print("****immBillingCycleId****", immBillingCycleId )
        print("****prodState****", prodState)
        adjustTime = AddDay(currentTime,1)
        print("****adjustTime****", adjustTime)
        if immBillingCycleId != dealBillingCycleId and prodState != 'E' and prodState != 'B':
            print("****ImmBillingCycleIdNotEqualDealBillingCycleId****")
            if currentTime != cycleBeginTime:
                chargeDays = diffdays(adjustTime,cycleBeginTime)
                print("****chargeDays****", chargeDays)
                print("****cycleDays****", cycleDays)
                mrcCharge = round(1.0 * mrcCharge * chargeDays / cycleDays)
                r.event.SetAttr(CYCLE_BEGIN_TIME,cycleBeginTime)
                r.event.SetAttr(CYCLE_END_TIME,adjustTime)
                r.event.SetAttr(461,cycleBeginTime)
                r.event.SetAttr(462,adjustTime)
        elif prodState != 'E' and prodState != 'B':
            print("****MainProdStateIsNotEorB****")
            refundDays = diffdays(cycleEndTime,adjustTime)
            print("****refundDays****", refundDays)
            print("****cycleDays****", cycleDays)
            mrcCharge = round(0 - 1.0 * mrcCharge * refundDays / cycleDays)
            r.event.SetAttr(CYCLE_BEGIN_TIME,adjustTime)
            r.event.SetAttr(CYCLE_END_TIME,cycleEndTime)
            r.event.SetAttr(461,adjustTime)
            r.event.SetAttr(462,cycleEndTime)
        else:
            print("****MainProdStateIsEorB****")
            mrcCharge = 0
        print("****PreRealBillingRecurringModeMRC****", mrcCharge)
        r.event.SetAttrList(42,int(mrcCharge))
        r.SetResult(mrcCharge)
    elif dealMode == 1:
        print("****OnlineRecurringMode****", dealMode)
        # new connection case  -- zentao: 1329
        processServiceType = int(r.event.GetAttrEx(1329).AsInteger() or 0)  # NEW_ORDER_REFUND_MODE  = 3
        billingCycleChangeType = int(r.event.GetAttrEx(921).AsInteger() or 0)
        print("****processServiceType(DPP)****", processServiceType)
        if processServiceType == 3:
            print("****EnterNewConnectionCase(DPP)****", processServiceType)
            completeDate = r.event.GetIndependProdCompletedDate()
            cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
            cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
            cycleDays = diffdays(cycleEndTime,cycleBeginTime)
            chargeDays = diffdays(cycleEndTime,completeDate)
            mrcCharge = round(1.0 * mrcCharge * chargeDays / cycleDays)
            print("****NewConnectionChargeDays****", chargeDays)
            print("****NewConnectionMrcCharge****", mrcCharge)
            # if isProrateFree flag is 1, then set charge to nagative value, also set acct item type id
            mrcCharge = -1 * int(mrcCharge) * isProrateFree
            if isProrateFree == 1:
                r.event.SetAttr(908,"5002,")   # MRC discount acct item type id: 5002
            print("****NewConnectionNewMrcCharge****", mrcCharge)
            r.event.SetAttrList(42, mrcCharge)
            r.event.SetAttr(862,currentTime)
            r.event.SetAttr(863,cycleEndTime)
        # termination/cancel recurring related product or addon case
        elif processServiceType in(11,12):
            print("****EnterTerminationCase(DPP)****", processServiceType)
            previousState = r.event.GetAttrEx(969).AsString()
            print("****previousState(DPP)****", previousState)
            agreementEffDate = int(r.event.GetAttrEx(2002).AsInteger() or -1)
            agreementExpDate = int(r.event.GetAttrEx(2003).AsInteger() or -1)
            print("****agreementEffDate****",agreementEffDate)
            print("****agreementExpDate****",agreementExpDate)
            terminationDate = r.event.GetAttrEx(3).AsInteger()
            print("****terminationDate****",terminationDate)
            cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
            cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
            cycleDays = diffdays(cycleEndTime,cycleBeginTime)
            print("****cycleBeginTime****",cycleBeginTime)
            print("****cycleEndTime****",cycleEndTime)
            print("****cycleDays****",cycleDays)
            # if agreement expire time is later than cycle begin time, then consider as valid agreement
            # because if there's valid agreement when running RecurrRate, then it will charge full MRC normally
            if (agreementExpDate >= cycleBeginTime) and (agreementEffDate != agreementExpDate):
                chargeDays = diffdays(cycleEndTime, AddDay(terminationDate,1))
                print('****AgreementValidAfterCycleBeginDate****')
                print('****chargeDays****',chargeDays)
                mrcCharge = round(0 - 1.0 * mrcCharge * chargeDays / cycleDays)
                r.event.SetAttr(862,AddDay(terminationDate,1))
            else:
                print('****NoValidAgreement****')
                if previousState == 'E':   # no agreement, and state is TWB before termination, no need to refund MRC
                    mrcCharge = 0
                else:                      # no agreement, and state is not TWB before termination, then refund MRC according to termination date
                    chargeDays = diffdays(cycleEndTime, AddDay(terminationDate,1))
                    print('****chargeDays****',chargeDays)
                    r.event.SetAttr(862,AddDay(terminationDate,1))
                    mrcCharge = round(0 - 1.0 * mrcCharge * chargeDays / cycleDays)
                    print('****mrcCharge****',mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(863,cycleEndTime)
        # Plan Conversion and Accont Change Case
        elif processServiceType in(13,7):
            if processServiceType == 13:
                print("****EnterChangePlanCase(DPP)****", processServiceType)
            else:
                print("****EnterAccountChangeCase(DPP)****", processServiceType)
            cycleBeginTime = r.event.GetAttrEx(862).AsInteger()
            cycleEndTime = r.event.GetAttrEx(863).AsInteger()
            currentTime = r.event.GetAttrEx(3).AsInteger()
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            subsPlanChangeState = r.event.GetAttrEx(1821).AsInteger()   # Plan Conversion Flag: 1: Old Plan, 2: New Plan
            print("****SubsPlanChangeState****",subsPlanChangeState)
            #beforeDays = diffdays(currentTime,cycleBeginTime)
            chargeDays = diffdays(cycleEndTime, currentTime)
            mrcCharge = round({1: -1.0, 2: 1.0}.get(subsPlanChangeState, 0) * mrcCharge * chargeDays / cycleDays)
            print("****SubsPlanChangeChargeDays****",chargeDays)
            print("****SubsPlanChangeMRC****",mrcCharge)
            # if isProrateFree flag is 1, then do not process
            if isProrateFree == 1:
                mrcCharge = 0
            r.event.SetAttrList(42, int(mrcCharge))
            if subsPlanChangeState == 1:
                r.event.SetAttr(862,currentTime + 180)
                r.event.SetAttr(863,cycleEndTime)
            elif subsPlanChangeState == 2:
                r.event.SetAttr(862,currentTime)
                r.event.SetAttr(863,cycleEndTime)
        # Change Billing Cycle Type Case
        elif processServiceType == 4 and billingCycleChangeType == 2:
            print("****EnterChangeBillingCycleCase(DPP)****", processServiceType)
            preBCCycleBeginTime = r.event.GetAttrEx(2009).AsInteger()
            preBCCycleEndTime = r.event.GetAttrEx(2010).AsInteger()
            cycleBeginTime = r.event.GetAttrEx(102).AsInteger()
            cycleEndTime = r.event.GetAttrEx(103).AsInteger()
            currentTime = r.event.GetAttrEx(3).AsInteger() 
            print("****currentTime****",currentTime)
            print("****preBCCycleBeginTime****", preBCCycleBeginTime)
            print("****preBCCycleEndTime****", preBCCycleEndTime)
            print("****cycleBeginTime****", cycleBeginTime)
            print("****cycleEndTime****", cycleEndTime)
            cycleDays = diffdays(preBCCycleEndTime, preBCCycleBeginTime)
            chargeDays = diffdays(preBCCycleEndTime, cycleEndTime)
            print("****BillingCycleChangeNewCycleDays****",cycleDays)
            print("****BillingCycleChangeNewCycleChargeDays****",chargeDays)
            mrcCharge = round(- 1.0 * mrcCharge * chargeDays / cycleDays)
            print("****BillingCycleChangeNewCycleMRC****",mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,cycleEndTime)
            r.event.SetAttr(863,preBCCycleEndTime)
        elif processServiceType in(14,2):
            print("****EnterSuspensionAndReactivationCase(DPP)****", processServiceType)
            # online refund/prorate mode, if with valid agreement, then ignore, otherwise process it
            currentTime = r.event.GetAttrEx(3).AsInteger()
            agreementEffDate = int(r.event.GetAttrEx(2002).AsInteger() or -1)
            agreementExpDate = int(r.event.GetAttrEx(2003).AsInteger() or -1)
            print("****currentTime****",currentTime)
            print("****agreementEffDate****",agreementEffDate)
            print("****agreementExpDate****",agreementExpDate)
            cycleBeginTime = r.event.GetAttrEx(102).AsInteger()
            cycleEndTime = r.event.GetAttrEx(103).AsInteger()
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            print("****cycleBeginTime****",cycleBeginTime)
            print("****cycleEndTime****",cycleEndTime)
            print("****cycleDays****",cycleDays)
            previousState = r.event.GetAttrEx(969).AsString()
            print("****previousState(DPP)****", previousState)
            # no refund for suspension date, charge mrc for reactivation date
            if not(agreementEffDate <= currentTime <= agreementExpDate and agreementEffDate != agreementExpDate):
                adjustTime = AddDay(currentTime, {14: 1, 2: 0}.get(processServiceType, 0)) 
                chargeDays = diffdays(cycleEndTime, adjustTime)
                mrcCharge = round({14: -1.0, 2: 1.0}.get(processServiceType, 0) * mrcCharge * chargeDays / cycleDays)
                print("****adjustTime****",adjustTime)
                print("****SuspensionAndReactivationChargeDays****",chargeDays)
                print("****SuspensionAndReactivationMRC****",mrcCharge)
                r.event.SetAttrList(42,int(mrcCharge))
                r.event.SetAttr(862,adjustTime)
                r.event.SetAttr(863,cycleEndTime)
            else:
                # if agreement will be expired in the billing cycle, then refund mrc to end of billing cycle
                if agreementExpDate >= cycleEndTime or agreementExpDate <= cycleBeginTime:
                    mrcCharge = 0
                else:
                    if agreementExpDate > currentTime:
                        print("****agreementExpAfter****")
                        chargeDays = diffdays(cycleEndTime, agreementExpDate)
                        print("****chargeDays****",chargeDays)
                        mrcCharge = round({14: -1.0, 2: 1.0}.get(processServiceType, 0) * mrcCharge * chargeDays / cycleDays)
                        print("****mrcCharge****",mrcCharge)
                        r.event.SetAttr(862,agreementExpDate)
                r.event.SetAttrList(42,int(mrcCharge))
                r.event.SetAttr(863,cycleEndTime)
                r.event.SetAttrList(42,int(mrcCharge))
            if processServiceType == 2 and previousState != 'E':
                mrcCharge = 0
        else:
            mrcCharge = 0
            r.event.SetAttrList(42, int(mrcCharge))
        r.event.SetAttr(REC_MUST_BENFIT_FLAG,1)
        r.SetResult(mrcCharge)