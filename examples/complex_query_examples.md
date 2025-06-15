# Complex Query Examples for Text2SQL Testing

This document contains various complex natural language queries that can be used to test the Text2SQL application's capabilities.

## 1. Multi-Table Joins with Aggregations

### Example 1: Sales Performance Analysis
**Natural Language Query:**
"Show me the total sales revenue by product category and region for the last quarter, including the number of orders and average order value, sorted by revenue descending"

**Expected SQL Pattern:**
```sql
SELECT 
    pc.CategoryName,
    r.RegionName,
    SUM(od.Quantity * od.UnitPrice) as TotalRevenue,
    COUNT(DISTINCT o.OrderID) as OrderCount,
    AVG(od.Quantity * od.UnitPrice) as AvgOrderValue
FROM Orders o
JOIN OrderDetails od ON o.OrderID = od.OrderID
JOIN Products p ON od.ProductID = p.ProductID
JOIN ProductCategories pc ON p.CategoryID = pc.CategoryID
JOIN Customers c ON o.CustomerID = c.CustomerID
JOIN Regions r ON c.RegionID = r.RegionID
WHERE o.OrderDate >= DATEADD(quarter, -1, GETDATE())
GROUP BY pc.CategoryName, r.RegionName
ORDER BY TotalRevenue DESC
```

## 2. Subqueries and Window Functions

### Example 2: Top Performing Customers
**Natural Language Query:**
"Find customers who have spent more than the average customer spending in their region, show their rank within their region and percentage difference from the regional average"

**Expected SQL Pattern:**
```sql
WITH CustomerSpending AS (
    SELECT 
        c.CustomerID,
        c.CustomerName,
        c.RegionID,
        SUM(od.Quantity * od.UnitPrice) as TotalSpent
    FROM Customers c
    JOIN Orders o ON c.CustomerID = o.CustomerID
    JOIN OrderDetails od ON o.OrderID = od.OrderID
    GROUP BY c.CustomerID, c.CustomerName, c.RegionID
),
RegionalAverage AS (
    SELECT 
        RegionID,
        AVG(TotalSpent) as AvgSpending
    FROM CustomerSpending
    GROUP BY RegionID
)
SELECT 
    cs.CustomerName,
    cs.TotalSpent,
    ra.AvgSpending,
    RANK() OVER (PARTITION BY cs.RegionID ORDER BY cs.TotalSpent DESC) as RegionalRank,
    ((cs.TotalSpent - ra.AvgSpending) / ra.AvgSpending * 100) as PercentAboveAverage
FROM CustomerSpending cs
JOIN RegionalAverage ra ON cs.RegionID = ra.RegionID
WHERE cs.TotalSpent > ra.AvgSpending
ORDER BY cs.RegionID, RegionalRank
```

## 3. Time Series Analysis

### Example 3: Month-over-Month Growth
**Natural Language Query:**
"Calculate the month-over-month revenue growth percentage for each product category over the past year, highlighting categories with consistent growth"

**Expected SQL Pattern:**
```sql
WITH MonthlyRevenue AS (
    SELECT 
        pc.CategoryName,
        YEAR(o.OrderDate) as OrderYear,
        MONTH(o.OrderDate) as OrderMonth,
        SUM(od.Quantity * od.UnitPrice) as MonthlyRevenue
    FROM Orders o
    JOIN OrderDetails od ON o.OrderID = od.OrderID
    JOIN Products p ON od.ProductID = p.ProductID
    JOIN ProductCategories pc ON p.CategoryID = pc.CategoryID
    WHERE o.OrderDate >= DATEADD(year, -1, GETDATE())
    GROUP BY pc.CategoryName, YEAR(o.OrderDate), MONTH(o.OrderDate)
),
GrowthCalculation AS (
    SELECT 
        CategoryName,
        OrderYear,
        OrderMonth,
        MonthlyRevenue,
        LAG(MonthlyRevenue) OVER (PARTITION BY CategoryName ORDER BY OrderYear, OrderMonth) as PrevMonthRevenue,
        CASE 
            WHEN LAG(MonthlyRevenue) OVER (PARTITION BY CategoryName ORDER BY OrderYear, OrderMonth) > 0
            THEN ((MonthlyRevenue - LAG(MonthlyRevenue) OVER (PARTITION BY CategoryName ORDER BY OrderYear, OrderMonth)) / LAG(MonthlyRevenue) OVER (PARTITION BY CategoryName ORDER BY OrderYear, OrderMonth)) * 100
            ELSE NULL
        END as GrowthPercent
    FROM MonthlyRevenue
)
SELECT 
    CategoryName,
    OrderYear,
    OrderMonth,
    MonthlyRevenue,
    GrowthPercent,
    CASE 
        WHEN COUNT(CASE WHEN GrowthPercent > 0 THEN 1 END) OVER (PARTITION BY CategoryName) >= 8 
        THEN 'Consistent Growth'
        ELSE 'Variable Growth'
    END as GrowthPattern
FROM GrowthCalculation
WHERE GrowthPercent IS NOT NULL
ORDER BY CategoryName, OrderYear, OrderMonth
```

## 4. Complex Filtering and Conditions

### Example 4: Customer Segmentation
**Natural Language Query:**
"Identify high-value customers who have made more than 10 orders in the past 6 months, spent over $5000, and haven't placed an order in the last 30 days (potential churn risk)"

**Expected SQL Pattern:**
```sql
WITH CustomerMetrics AS (
    SELECT 
        c.CustomerID,
        c.CustomerName,
        c.Email,
        COUNT(o.OrderID) as OrderCount,
        SUM(od.Quantity * od.UnitPrice) as TotalSpent,
        MAX(o.OrderDate) as LastOrderDate,
        DATEDIFF(day, MAX(o.OrderDate), GETDATE()) as DaysSinceLastOrder
    FROM Customers c
    LEFT JOIN Orders o ON c.CustomerID = o.CustomerID
    LEFT JOIN OrderDetails od ON o.OrderID = od.OrderID
    WHERE o.OrderDate >= DATEADD(month, -6, GETDATE())
    GROUP BY c.CustomerID, c.CustomerName, c.Email
)
SELECT 
    CustomerName,
    Email,
    OrderCount,
    TotalSpent,
    LastOrderDate,
    DaysSinceLastOrder,
    'High Value Churn Risk' as CustomerSegment
FROM CustomerMetrics
WHERE OrderCount > 10
    AND TotalSpent > 5000
    AND DaysSinceLastOrder > 30
ORDER BY TotalSpent DESC, DaysSinceLastOrder DESC
```

## 5. Advanced Analytics

### Example 5: Product Recommendation Analysis
**Natural Language Query:**
"Find products that are frequently bought together, showing product pairs with their co-purchase frequency and confidence score where confidence is above 30%"

**Expected SQL Pattern:**
```sql
WITH ProductPairs AS (
    SELECT 
        od1.ProductID as Product1,
        od2.ProductID as Product2,
        COUNT(DISTINCT od1.OrderID) as CoPurchaseCount
    FROM OrderDetails od1
    JOIN OrderDetails od2 ON od1.OrderID = od2.OrderID
    WHERE od1.ProductID < od2.ProductID  -- Avoid duplicates and self-pairs
    GROUP BY od1.ProductID, od2.ProductID
),
ProductFrequency AS (
    SELECT 
        ProductID,
        COUNT(DISTINCT OrderID) as TotalOrders
    FROM OrderDetails
    GROUP BY ProductID
),
ConfidenceScores AS (
    SELECT 
        pp.Product1,
        pp.Product2,
        p1.ProductName as Product1Name,
        p2.ProductName as Product2Name,
        pp.CoPurchaseCount,
        pf1.TotalOrders as Product1Orders,
        pf2.TotalOrders as Product2Orders,
        (CAST(pp.CoPurchaseCount AS FLOAT) / pf1.TotalOrders * 100) as ConfidenceScore1to2,
        (CAST(pp.CoPurchaseCount AS FLOAT) / pf2.TotalOrders * 100) as ConfidenceScore2to1
    FROM ProductPairs pp
    JOIN Products p1 ON pp.Product1 = p1.ProductID
    JOIN Products p2 ON pp.Product2 = p2.ProductID
    JOIN ProductFrequency pf1 ON pp.Product1 = pf1.ProductID
    JOIN ProductFrequency pf2 ON pp.Product2 = pf2.ProductID
)
SELECT 
    Product1Name,
    Product2Name,
    CoPurchaseCount,
    ROUND(ConfidenceScore1to2, 2) as ConfidenceScore1to2,
    ROUND(ConfidenceScore2to1, 2) as ConfidenceScore2to1,
    ROUND((ConfidenceScore1to2 + ConfidenceScore2to1) / 2, 2) as AvgConfidence
FROM ConfidenceScores
WHERE ConfidenceScore1to2 > 30 OR ConfidenceScore2to1 > 30
ORDER BY AvgConfidence DESC, CoPurchaseCount DESC
```

## 6. Hierarchical Data and Recursive Queries

### Example 6: Organizational Hierarchy
**Natural Language Query:**
"Show the complete organizational hierarchy starting from the CEO, including each employee's level, total number of subordinates (direct and indirect), and their department's total headcount"

**Expected SQL Pattern:**
```sql
WITH EmployeeHierarchy AS (
    -- Anchor: Start with CEO (assuming no manager)
    SELECT 
        EmployeeID,
        EmployeeName,
        ManagerID,
        DepartmentID,
        1 as Level,
        CAST('/' + CAST(EmployeeID AS VARCHAR) + '/' AS VARCHAR(1000)) as HierarchyPath
    FROM Employees
    WHERE ManagerID IS NULL
    
    UNION ALL
    
    -- Recursive: Get all subordinates
    SELECT 
        e.EmployeeID,
        e.EmployeeName,
        e.ManagerID,
        e.DepartmentID,
        eh.Level + 1,
        CAST(eh.HierarchyPath + CAST(e.EmployeeID AS VARCHAR) + '/' AS VARCHAR(1000))
    FROM Employees e
    INNER JOIN EmployeeHierarchy eh ON e.ManagerID = eh.EmployeeID
),
DepartmentHeadcount AS (
    SELECT 
        DepartmentID,
        COUNT(*) as DeptHeadcount
    FROM Employees
    GROUP BY DepartmentID
),
SubordinateCounts AS (
    SELECT 
        eh1.EmployeeID,
        COUNT(eh2.EmployeeID) as TotalSubordinates
    FROM EmployeeHierarchy eh1
    LEFT JOIN EmployeeHierarchy eh2 ON eh2.HierarchyPath LIKE eh1.HierarchyPath + '%'
        AND eh2.EmployeeID != eh1.EmployeeID
    GROUP BY eh1.EmployeeID
)
SELECT 
    REPLICATE('  ', eh.Level - 1) + eh.EmployeeName as HierarchicalName,
    eh.Level,
    d.DepartmentName,
    ISNULL(sc.TotalSubordinates, 0) as TotalSubordinates,
    dh.DeptHeadcount as DepartmentHeadcount
FROM EmployeeHierarchy eh
JOIN Departments d ON eh.DepartmentID = d.DepartmentID
JOIN DepartmentHeadcount dh ON eh.DepartmentID = dh.DepartmentID
LEFT JOIN SubordinateCounts sc ON eh.EmployeeID = sc.EmployeeID
ORDER BY eh.HierarchyPath
```

## Simple Test Queries (for initial testing)

### Basic Queries
1. "Show me all customers from New York"
2. "What are the top 5 selling products this month?"
3. "List all orders placed yesterday"
4. "Find customers who haven't placed an order in 90 days"

### Medium Complexity
1. "Show total sales by region for the current year"
2. "Which products have the highest profit margin?"
3. "Find the average order value by customer segment"
4. "Show monthly sales trends for the past 6 months"

## Usage Instructions

1. Start with simple queries to test basic functionality
2. Progress to medium complexity queries to test joins and aggregations
3. Use complex queries to test advanced features like CTEs, window functions, and subqueries
4. Monitor the LLM model selection (o4-mini vs GPT-4.1) based on query complexity
5. Check error correction capabilities by intentionally using ambiguous terms
6. Validate results against expected SQL patterns

## Testing Checklist

- [ ] Basic SELECT statements work correctly
- [ ] Multi-table JOINs are handled properly
- [ ] Aggregate functions (SUM, COUNT, AVG) work
- [ ] Date/time filtering functions correctly
- [ ] Window functions are supported
- [ ] CTEs (Common Table Expressions) work
- [ ] Subqueries are handled correctly
- [ ] Error correction activates for invalid queries
- [ ] LLM routing works (simple queries → o4-mini, complex → GPT-4.1)
- [ ] Results are formatted correctly in the UI
- [ ] Logging captures all steps appropriately
