def main(r):
    originalMRC = &MRC_CHARGE&
    prorateFlag = &PRORATE_FLAG&
    # 获取定制化租费
    overWrittenMRC = float(r.event.GetPricePlanAttrValue('EXP_OVERWRITTEN_MRC') or '-1')
    print("****overWrittenMRC(IPP)****", overWrittenMRC)
    if overWrittenMRC == -1:
        mrcCharge = originalMRC
    else:
        mrcCharge = overWrittenMRC
    mrcCharge = int(mrcCharge or 0) * 10000
    print("****originalMRC(IPP)****", mrcCharge)
    cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
    cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
    cycleDays = diffdays(cycleEndTime,cycleBeginTime)
    # 获取租费模式，正常收租或者租费补退
    dealMode = int(r.event.GetAttrEx(959).AsInteger() or 0)
    prodState = r.event.GetIndependProdState()
    print("****prodState****", prodState)
    if dealMode == 0 or prorateFlag == 'N':   #正常周期费算费场景
        currentTime = r.event.GetAttrEx(3).AsInteger()
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
    elif dealMode == 1 and prorateFlag == 'Y':
        processServiceType = int(r.event.GetAttrEx(1329).AsInteger() or 0)  
        billingCycleChangeType = int(r.event.GetAttrEx(921).AsInteger() or 0)
        print("****processServiceType(IPP)****", processServiceType)
        if processServiceType == 3:   # NEW_ORDER_REFUND_MODE  = 3
            print("****EnterNewOrderCase(IPP)****", processServiceType)
            currentTime = r.event.GetAttrEx(3).AsInteger()
            cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
            cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
            cycleDays = diffdays(cycleEndTime,cycleBeginTime)
            chargeDays = diffdays(cycleEndTime,currentTime)
            mrcCharge = round(1.0 * mrcCharge * chargeDays / cycleDays)
            print("****cycleDays****", cycleDays)
            print("****chargeDays****", chargeDays)
            print("****NewOrderChargeDays****", chargeDays)
            print("****NewOrderMrcCharge****", mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,currentTime)
            r.event.SetAttr(863,cycleEndTime)
        # 主产品拆机/依赖产品取消/IPP取消场景
        elif processServiceType in(11,12):
            print("****EnterTerminationCase(IPP)****", processServiceType)
            terminationDate = r.event.GetAttrEx(3).AsInteger()   # 取拆机时间
            cycleBeginTime = r.event.GetAttrEx(102).AsInteger()
            cycleEndTime = r.event.GetAttrEx(103).AsInteger()
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            chargeDays = diffdays(cycleEndTime, AddDay(terminationDate, 1))  # 拆机当天不算租费
            mrcCharge = round(0 - 1.0 * mrcCharge * chargeDays / cycleDays)
            print("****cycleDays****", cycleDays)
            print("****TerminationChargeDays****", chargeDays)
            print("****TerminationMrcCharge****", mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,AddDay(terminationDate, 1))
            r.event.SetAttr(863,cycleEndTime)
        # 套餐切换场景
        elif processServiceType == 13:
            print("****EnterChangePlanCase(IPP)****", processServiceType)
            cycleBeginTime = r.event.GetAttrEx(862).AsInteger()         #周期开始时间
            cycleEndTime = r.event.GetAttrEx(863).AsInteger()           #周期结束时间
            currentTime = r.event.GetAttrEx(3).AsInteger()              #获取算费时间
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            subsPlanChangeState = r.event.GetAttrEx(1821).AsInteger()   #订户套餐切换标识
            print("****SubsPlanChangeState****",subsPlanChangeState)
            chargeDays = diffdays(cycleEndTime, currentTime)              # 触发补收时间与账期结束时间相差时长
            mrcCharge = round({1: -1.0, 2: 1.0}.get(subsPlanChangeState, 0) * mrcCharge * chargeDays / cycleDays)
            print("****SubsPlanChangeChargeDays****",chargeDays)
            print("****SubsPlanChangeMRC****",mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,currentTime)
            r.event.SetAttr(863,cycleEndTime)
        # 账期切换场景
        elif processServiceType == 4 and billingCycleChangeType == 2:  #帐期末切换补收租费子场景
            print("****EnterChangeBillingCycleCase(IPP)****", processServiceType)
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
        # 双停和复机场景
        elif processServiceType in(14,2):
            print("****EnterSuspensionAndReactivationCase(IPP)****", processServiceType)
            #判断是否有合约
            currentTime = r.event.GetAttrEx(3).AsInteger()
            agreementEffDate = int(r.event.GetAttrEx(2002).AsInteger() or -1)
            agreementExpDate = int(r.event.GetAttrEx(2003).AsInteger() or -1)
            print("****currentTime****",currentTime)
            print("****agreementEffDate****",agreementEffDate)
            print("****agreementExpDate****",agreementExpDate)
            if (agreementEffDate == -1 and agreementExpDate == -1) or (currentTime < agreementEffDate) or (currentTime > agreementExpDate) or (agreementEffDate == agreementExpDate):
                cycleBeginTime = r.event.GetAttrEx(102).AsInteger()
                cycleEndTime = r.event.GetAttrEx(103).AsInteger()
                cycleDays = diffdays(cycleEndTime, cycleBeginTime)
                adjustTime = AddDay(currentTime, {14: 1, 2: 0}.get(processServiceType, 0)) 
                chargeDays = diffdays(cycleEndTime, adjustTime)
                mrcCharge = round({14: -1.0, 2: 1.0}.get(processServiceType, 0) * mrcCharge * chargeDays / cycleDays)
                print("****SuspensionAndReactivationChargeDays****",chargeDays)
                print("****SuspensionAndReactivationMRC****",mrcCharge)
                r.event.SetAttrList(42,int(mrcCharge))
                r.event.SetAttr(862,adjustTime)
                r.event.SetAttr(863,cycleEndTime)
            else:
                mrcCharge = 0
                r.event.SetAttrList(42,int(mrcCharge))
        else:
            charge = mrcCharge
            r.event.SetAttrList(42, int(mrcCharge))
        r.event.SetAttr(REC_MUST_BENFIT_FLAG,1)
        r.SetResult(mrcCharge)
