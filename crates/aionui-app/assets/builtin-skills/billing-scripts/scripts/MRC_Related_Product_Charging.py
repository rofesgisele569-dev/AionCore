def main(r):
    print("****RelatedProduct****")
    # RelatedProductId = r.event.GetAttrEx(972).AsInteger()    # IMS IP 1342
    RelatedProductId = &INDEP_PROD_SPEC_ID&
    subsId = r.event.GetAttrEx(201).AsInteger()
    currentTime = r.event.GetAttrEx(EVENT_BEGIN_TIME).AsInteger()
    subsPlanId = r.event.GetAttrEx(112).AsInteger()
    print("****subsPlanId****", subsPlanId)
    # 获取依赖产品实例化的租费信息，对于依赖产品使用
    overWrittenMRC  = r.event.GetDependProdAttrValueByDependProdCode("EXP_OVERWRITTEN_MRC",RelatedProductId,currentTime)
    #overWrittenMRC = r.event.GetPricePlanAttrValueBySubsUppInstId('EXP_OVERWRITTEN_MRC',currentTime,)
    if overWrittenMRC == 'NULL' or overWrittenMRC is None or len(overWrittenMRC) == 0:
        overWrittenMRC = 0
    else:
        overWrittenMRC = int(overWrittenMRC)
    print("****overWrittenMRC4RelatedProduct****", overWrittenMRC)
    print("****subsId****", subsId)
    mrcCharge = int(overWrittenMRC) * 10000
    # 获取租费模式，正常收租或者租费补退
    dealMode = int(r.event.GetAttrEx(959).AsInteger() or 0)
    if dealMode == 0:   #正常周期费算费场景
        r.event.SetAttrList(42,mrcCharge)
        r.SetResult(mrcCharge)
    elif dealMode == 1:
        # 账期中开户预收场景 -- zentao: 1329
        processServiceType = int(r.event.GetAttrEx(1329).AsInteger() or 0)
        billingCycleChangeType = int(r.event.GetAttrEx(921).AsInteger() or 0)
        print("****processServiceType(RP)****", processServiceType)
        if processServiceType == 3:
            print("****EnterNewConnectionCase(RP)****", processServiceType)
            #completeDate = r.event.GetIndependProdCompletedDate()
            currentTime = r.event.GetAttrEx(EVENT_BEGIN_TIME).AsInteger()
            cycleBeginTime = r.event.GetAttrEx(CYCLE_BEGIN_TIME).AsInteger()
            cycleEndTime = r.event.GetAttrEx(CYCLE_END_TIME).AsInteger()
            cycleDays = diffdays(cycleEndTime,cycleBeginTime)
            chargeDays = diffdays(cycleEndTime,currentTime)
            mrcCharge = round(1.0 * mrcCharge * chargeDays / cycleDays)
            print("****currentTime****", currentTime)
            print("****cycleBeginTime****", cycleBeginTime)
            print("****cycleEndTime****", cycleEndTime)
            print("****NewOrderChargeDays****", chargeDays)
            print("****NewOrdercycleDays****", cycleDays)
            print("****NewOrderMrcCharge****", mrcCharge)
            print("****mrcCharge1****", mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,currentTime)
            r.event.SetAttr(863,cycleEndTime)
        # 主产品拆机/依赖产品取消/IPP取消场景
        elif processServiceType in(11,12):
            # 获取依赖产品实例化的租费信息，对于依赖产品使用
            # 去订购或者拆机场景，时间需要减一秒，否则找不到资料
            overWrittenMRC  = r.event.GetDependProdAttrValueByDependProdCode("EXP_OVERWRITTEN_MRC",RelatedProductId,currentTime -1)
            if overWrittenMRC == 'NULL' or overWrittenMRC is None or len(overWrittenMRC) == 0:
                overWrittenMRC = 0
            else:
                overWrittenMRC = int(overWrittenMRC)
            print("****overWrittenMRC4RelatedProduct****", overWrittenMRC)
            mrcCharge = int(overWrittenMRC) * 10000
            print("****EnterTerminationCase(RP)****", processServiceType)
            terminationDate = r.event.GetAttrEx(3).AsInteger()   # 取拆机时间
            cycleBeginTime = r.event.GetAttrEx(102).AsInteger()
            cycleEndTime = r.event.GetAttrEx(103).AsInteger()
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            chargeDays = diffdays(cycleEndTime, AddDay(terminationDate, 1))  # 拆机当天不算租费
            mrcCharge = round(0 - 1.0 * mrcCharge * chargeDays / cycleDays)
            print("****TerminationChargeDays****", chargeDays)
            print("****TerminationMrcCharge****", mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,AddDay(terminationDate, 1))
            r.event.SetAttr(863,cycleEndTime)
        # 套餐切换场景
        elif processServiceType == 13:
            print("****EnterChangePlanCase(RP)****", processServiceType)
            cycleBeginTime = r.event.GetAttrEx(862).AsInteger()         #周期开始时间
            cycleEndTime = r.event.GetAttrEx(863).AsInteger()           #周期结束时间
            currentTime = r.event.GetAttrEx(3).AsInteger()              #获取算费时间
            cycleDays = diffdays(cycleEndTime, cycleBeginTime)
            subsPlanChangeState = r.event.GetAttrEx(1821).AsInteger()   #订户套餐切换标识
            print("****SubsPlanChangeState****",subsPlanChangeState)
            #beforeDays = diffdays(currentTime,cycleBeginTime)          # 触发补收时间与账期开始时间相差时长
            chargeDays = diffdays(cycleEndTime, currentTime)            # 触发补收时间与账期结束时间相差时长
            mrcCharge = round({1: -1.0, 2: 1.0}.get(subsPlanChangeState, 0) * mrcCharge * chargeDays / cycleDays)
            print("****SubsPlanChangeChargeDays****",chargeDays)
            print("****SubsPlanChangeMRC****",mrcCharge)
            r.event.SetAttrList(42,int(mrcCharge))
            r.event.SetAttr(862,currentTime)
            r.event.SetAttr(863,cycleEndTime)
        # 账期切换场景
        elif processServiceType == 4 and billingCycleChangeType == 2:  #帐期末切换补收租费子场景
            print("****EnterChangeBillingCycleCase(RP)****", processServiceType)
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
            print("****EnterSuspensionAndReactivationCase(RP)****", processServiceType)
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
            print("****mrcCharge2****",mrcCharge)
            r.event.SetAttrList(42, int(mrcCharge))
        r.event.SetAttr(REC_MUST_BENFIT_FLAG,1)
        print("****mrcCharge3****",mrcCharge)
        r.SetResult(int(mrcCharge))