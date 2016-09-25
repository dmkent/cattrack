/*
  periodName: 
    Number followed by multiplier. Multiplier is:
       W - week
       M, MS - month 
       Q, QS - quarter
       A, AS - annual
  For example:
      PeriodMapper('2W', )
*/
export class PeriodMapper {
    constructor(public periodName: string,
                public refDate?: Date){
        if (refDate === undefined){
            this.refDate = new Date();
        }
    }

    asDateRange(): Date[] {
        let fromDate = new Date();
        let toDate = new Date();
        return [fromDate, toDate]
    }
}