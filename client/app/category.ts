export class Category {
    id: number;
    name: string;
}

export class SplitCategory {
    category: number;
    amount: number;
}

export class CategorySummary {
    category: number;
    category_name: string;
    total: number;
}