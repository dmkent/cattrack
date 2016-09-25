export class Transaction {
    id: number;
    when: Date;
    description: string;
    amount: number;
    category: number;
    category_name: string;
    account: number;
}

export class TransactionPage{
    count: number;
    transactions: Transaction[];
}