# 架構選型筆記：傳統三層架構 vs Vertical Slice Architecture (VSA)

> 本文件整理「傳統分層架構（N-Layer / N-Tier）」與「垂直切片架構（Vertical Slice Architecture, VSA）」的差異、範例、適用場景與業界觀點，作為團隊未來評估架構選型時的參考。
>
> 範例語言：C# / .NET（泛型範例，與任何具體專案脫鉤，可直接分享給外部參考）。

---

## 目錄

1. [前言](#前言)
2. [傳統三層架構（Layered Architecture）](#傳統三層架構layered-architecture)
3. [Vertical Slice Architecture (VSA)](#vertical-slice-architecture-vsa)
4. [兩者比較](#兩者比較)
5. [適用場景](#適用場景)
6. [業界知名人士的看法](#業界知名人士的看法)
7. [常見誤解 / FAQ](#常見誤解--faq)
8. [中間路線：VSA-lite（Feature Folder，不上 CQRS/MediatR）](#中間路線vsa-litefeature-folder不上-cqrsmediatr)
9. [Blazor Server 的特殊考量](#blazor-server-的特殊考量)
10. [決策檢查表](#決策檢查表)
11. [延伸閱讀](#延伸閱讀)

---

## 前言

過去十幾年，.NET 後端專案的預設架構幾乎都是「三層架構」：Controller（或 Presentation）→ Service（Business Logic）→ Repository（Data Access）。這套架構穩定、好教、好懂，幾乎是每個新手教材的起手式。

但隨著微服務、CQRS、DDD 等概念普及，加上 Jimmy Bogard（MediatR 作者）、Milan Jovanović、Derek Comartin（CodeOpinion）等人持續推廣，**Vertical Slice Architecture（VSA）** 這幾年在 .NET 社群討論度大幅上升，成為傳統分層之外的重要替代方案。

本文件的目的：把兩種架構講清楚，讓「要不要換架構」變成一個有根據的決定，而不是跟風。

---

## 傳統三層架構（Layered Architecture）

### 概念

以「技術職責」（Technical Responsibility）切分程式碼：所有 Controller 放一起、所有 Service 放一起、所有 Repository 放一起。**同一層的東西放一起，同一個功能的東西反而被拆散在不同層。**

```
┌─────────────────────────┐
│   Presentation Layer     │  Controllers / Pages
├─────────────────────────┤
│   Business Logic Layer   │  Services
├─────────────────────────┤
│   Data Access Layer      │  Repositories
├─────────────────────────┤
│      Database            │
└─────────────────────────┘
```

依賴方向永遠是「上層依賴下層」：Controller 依賴 Service，Service 依賴 Repository。

### 資料夾結構範例

```
MyApp/
├── Controllers/
│   ├── OrderController.cs
│   ├── ProductController.cs
│   └── CustomerController.cs
├── Services/
│   ├── IOrderService.cs
│   ├── OrderService.cs
│   ├── IProductService.cs
│   └── ProductService.cs
├── Repositories/
│   ├── IOrderRepository.cs
│   ├── OrderRepository.cs
│   ├── IProductRepository.cs
│   └── ProductRepository.cs
├── DTOs/
│   ├── OrderDto.cs
│   ├── CreateOrderRequest.cs
│   └── ProductDto.cs
└── Models/
    ├── Order.cs
    └── Product.cs
```

> 想改「訂單建立」這一個功能，得同時打開 `OrderController.cs`、`IOrderService.cs` / `OrderService.cs`、`IOrderRepository.cs` / `OrderRepository.cs`、`CreateOrderRequest.cs` —— 一個功能，散在 4～5 個資料夾。

### 程式碼範例

```csharp
// Controllers/OrderController.cs
[ApiController]
[Route("api/orders")]
public class OrderController : ControllerBase
{
    private readonly IOrderService _orderService;

    public OrderController(IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpPost]
    public async Task<ActionResult<OrderDto>> CreateOrder(CreateOrderRequest request)
    {
        var order = await _orderService.CreateOrderAsync(request);
        return CreatedAtAction(nameof(GetOrder), new { id = order.Id }, order);
    }

    [HttpGet("{id}")]
    public async Task<ActionResult<OrderDto>> GetOrder(int id)
    {
        var order = await _orderService.GetOrderByIdAsync(id);
        return order is null ? NotFound() : Ok(order);
    }
}

// Services/OrderService.cs
public class OrderService : IOrderService
{
    private readonly IOrderRepository _orderRepository;
    private readonly IProductRepository _productRepository;

    public OrderService(IOrderRepository orderRepository, IProductRepository productRepository)
    {
        _orderRepository = orderRepository;
        _productRepository = productRepository;
    }

    public async Task<OrderDto> CreateOrderAsync(CreateOrderRequest request)
    {
        var product = await _productRepository.GetByIdAsync(request.ProductId)
            ?? throw new InvalidOperationException("Product not found");

        var order = new Order
        {
            ProductId = product.Id,
            Quantity = request.Quantity,
            TotalPrice = product.Price * request.Quantity,
            CreatedAt = DateTime.UtcNow
        };

        await _orderRepository.AddAsync(order);
        return new OrderDto(order.Id, order.TotalPrice, order.CreatedAt);
    }

    public async Task<OrderDto?> GetOrderByIdAsync(int id)
    {
        var order = await _orderRepository.GetByIdAsync(id);
        return order is null ? null : new OrderDto(order.Id, order.TotalPrice, order.CreatedAt);
    }
}

// Repositories/OrderRepository.cs
public class OrderRepository : IOrderRepository
{
    private readonly AppDbContext _context;

    public OrderRepository(AppDbContext context) => _context = context;

    public async Task AddAsync(Order order)
    {
        _context.Orders.Add(order);
        await _context.SaveChangesAsync();
    }

    public Task<Order?> GetByIdAsync(int id) =>
        _context.Orders.FirstOrDefaultAsync(o => o.Id == id);
}
```

### 優點

| 優點 | 說明 |
|---|---|
| 學習曲線低 | 幾乎所有 .NET 教材、面試題都是這套，新人上手快 |
| 職責分離清楚 | Controller 只管 HTTP、Service 只管邏輯、Repository 只管資料，符合傳統 SOLID / SRP 直覺 |
| 容易套用通用抽象 | `IRepository<T>`、`IService<T>` 這類通用介面很容易在這個結構下實作 |
| 團隊分工直覺 | 前端組碰 Controller/DTO，後端組碰 Service/Repository，分工邊界清楚 |
| 生態成熟 | 幾乎所有 ORM、DI 容器、範本都預設支援這種結構 |

### 缺點

| 缺點 | 說明 |
|---|---|
| **水平依賴散開** | 改一個功能要跳好幾個資料夾，違反「相關的東西放一起」的內聚原則 |
| **共用邏輯容易長成巨獸** | `OrderService` 常常一個檔案塞了 10 種操作（建立、查詢、取消、退款…），檔案越長越難維護 |
| **抽象常常是為了套框架而套，不是為了解決問題** | 很多小專案為了「遵循三層」硬是加了一層 Repository，即使底下就是薄薄一層 EF Core 呼叫，沒有實質價值 |
| **跨功能耦合風險高** | `OrderService` 依賴 `ProductRepository`，時間久了 Service 之間互相依賴變成蜘蛛網 |
| **難以依功能拆分團隊/微服務** | 因為程式碼是「按技術層」切的，要拆成獨立可部署的功能模組時，往往要花很大力氣重新梳理 |

---

## Vertical Slice Architecture (VSA)

### 概念

VSA 由 **Jimmy Bogard**（MediatR 作者）在 2016 年一篇部落格文章 *"Vertical Slice Architecture"* 中提出並推廣。核心主張：

> "Group code by feature, not by technical layer. Minimize coupling between slices, and don't worry about coupling within a slice."
> —— Jimmy Bogard

以「業務功能」（Feature）切分程式碼：一個功能（例如「建立訂單」）從進入點到資料庫存取，全部放在同一個資料夾。**每個切片（Slice）是相對獨立、可以各自演化的最小單位**，切片之間才需要小心管理耦合，切片內部反而不用過度分層。

```
┌──────────┬──────────┬──────────┐
│  Create  │   Get    │  Cancel  │
│  Order   │  Order   │  Order   │
│ (Slice)  │ (Slice)  │ (Slice)  │
├──────────┴──────────┴──────────┤
│         Shared Kernel           │  DbContext, Auth, Logging
└─────────────────────────────────┘
```

### 資料夾結構範例

```
MyApp/
├── Features/
│   ├── Orders/
│   │   ├── CreateOrder/
│   │   │   ├── CreateOrderEndpoint.cs
│   │   │   ├── CreateOrderCommand.cs
│   │   │   ├── CreateOrderHandler.cs
│   │   │   └── CreateOrderValidator.cs
│   │   ├── GetOrder/
│   │   │   ├── GetOrderEndpoint.cs
│   │   │   ├── GetOrderQuery.cs
│   │   │   └── GetOrderHandler.cs
│   │   └── CancelOrder/
│   │       ├── CancelOrderEndpoint.cs
│   │       ├── CancelOrderCommand.cs
│   │       └── CancelOrderHandler.cs
│   └── Products/
│       ├── CreateProduct/
│       └── GetProductList/
├── Shared/
│   ├── AppDbContext.cs
│   ├── Entities/
│   │   ├── Order.cs
│   │   └── Product.cs
│   └── Middleware/
└── Program.cs
```

> 想改「訂單建立」這一個功能，只要打開 `Features/Orders/CreateOrder/` 這一個資料夾，裡面 4 個檔案就是這個功能的全部。不會動到 `GetOrder`、`CancelOrder`。

### 程式碼範例（搭配 MediatR，最常見的做法）

```csharp
// Features/Orders/CreateOrder/CreateOrderCommand.cs
public record CreateOrderCommand(int ProductId, int Quantity) : IRequest<OrderDto>;

// Features/Orders/CreateOrder/CreateOrderHandler.cs
public class CreateOrderHandler : IRequestHandler<CreateOrderCommand, OrderDto>
{
    private readonly AppDbContext _db;

    public CreateOrderHandler(AppDbContext db) => _db = db;

    public async Task<OrderDto> Handle(CreateOrderCommand request, CancellationToken ct)
    {
        var product = await _db.Products.FindAsync([request.ProductId], ct)
            ?? throw new InvalidOperationException("Product not found");

        var order = new Order
        {
            ProductId = product.Id,
            Quantity = request.Quantity,
            TotalPrice = product.Price * request.Quantity,
            CreatedAt = DateTime.UtcNow
        };

        _db.Orders.Add(order);
        await _db.SaveChangesAsync(ct);

        return new OrderDto(order.Id, order.TotalPrice, order.CreatedAt);
    }
}

// Features/Orders/CreateOrder/CreateOrderEndpoint.cs（Minimal API）
public static class CreateOrderEndpoint
{
    public static void MapCreateOrder(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/orders", async (CreateOrderCommand command, ISender sender) =>
        {
            var result = await sender.Send(command);
            return Results.Created($"/api/orders/{result.Id}", result);
        });
    }
}
```

**注意**：`CreateOrderHandler` 直接注入 `AppDbContext`，沒有額外的 Repository 抽象層——這是 VSA 的典型做法：**每個切片自己決定要不要抽象，不用為了套框架而套框架**。如果 `GetOrder` 這個查詢切片邏輯很簡單，甚至可以直接用 Dapper 寫一條 SQL，不用跟 `CreateOrder` 共用同一套資料存取邏輯。

### 優點

| 優點 | 說明 |
|---|---|
| **高內聚** | 一個功能的所有程式碼都在同一個資料夾，改動範圍清楚、review 容易 |
| **降低不必要的耦合** | 切片之間不強迫共用抽象，`CreateOrder` 要改資料存取方式，不會波及 `GetOrder` |
| **符合開放封閉原則的實務精神** | 新增功能 = 新增一個資料夾，幾乎不用改到既有程式碼，降低 regression 風險 |
| **適合 CQRS** | Command（寫）跟 Query（讀）本來就該用不同模型，VSA 天然契合 |
| **適合 Feature Team 組織** | 一個團隊/工程師可以完整擁有一個垂直切片，減少跨團隊協調 |
| **減少「假抽象」** | 不會因為「三層架構規定要有 Repository」而寫出沒有實質意義的轉接層 |

### 缺點

| 缺點 | 說明 |
|---|---|
| **共用邏輯需要額外紀律** | 沒有強制分層，重複邏輯容易悄悄長出來，需要團隊自律定期抽取共用邏輯到 `Shared/` |
| **學習曲線與慣例成本** | 團隊要先理解「這不是亂放」，需要文件與 code review 把關，否則新人可能誤解為沒有架構 |
| **常被跟 CQRS/MediatR 綁在一起討論**，容易誤以為「VSA = 一定要上 MediatR」，增加不必要的套件依賴與間接層 | 其實 VSA 是「資料夾組織方式」，MediatR 只是最常見但非必須的搭配 |
| **對簡單 CRUD 應用可能過度設計** | 如果應用邏輯簡單、團隊小，切片邊界反而變成不必要的儀式感 |
| **工具/範本支援較新** | 官方 `dotnet new` 範本不含 VSA，需要自己或用社群範本建立慣例 |

---

## 兩者比較

| 面向 | 傳統三層架構 | VSA |
|---|---|---|
| 切分依據 | 技術層（Controller/Service/Repo） | 業務功能（Feature） |
| 一個功能的程式碼 | 分散在多個資料夾 | 集中在一個資料夾 |
| 層與層之間耦合 | 高（上層依賴下層，處處共用） | 低（切片間各自獨立） |
| 切片/層內部彈性 | 低（每層要符合同一套介面規範） | 高（各切片可自行決定實作方式） |
| 新增功能的改動範圍 | 可能牽動多層既有檔案 | 通常只新增資料夾，不動舊碼 |
| 重複程式碼風險 | 低（共用 Service/Repo 天然共用） | 中～高（需自律抽取共用邏輯） |
| 適合團隊規模/組織 | 依技術職能分工的團隊 | 依功能垂直分工的 Feature Team |
| 常見搭配技術 | Controller + AutoMapper + Repository | Minimal API / MediatR / FastEndpoints + CQRS |
| 學習資源成熟度 | 非常成熟，幾乎所有教材預設 | 近年成長中，權威文章/範本相對少 |
| 官方範本支援 | 有（`dotnet new webapi/mvc`） | 無官方範本，需自建慣例 |

---

## 適用場景

### 適合傳統三層架構

- 企業內部系統、後台管理系統、CRUD 為主的業務應用（例如採購/簽核/報表類系統）
- 團隊按技術職能分工（前端組、後端組、DB 組）
- 團隊成員對三層架構已經很熟悉，追求穩定與可預測性優先於彈性
- 專案邏輯相對簡單，功能之間本來就高度共用（例如都繞著同一個 `Customer` 實體做操作）

### 適合 VSA

- API 導向、CQRS 明顯的系統（讀寫模型差異大，例如報表查詢 vs 交易寫入）
- 微服務或未來可能拆分微服務的單體（Modular Monolith），需要清楚的功能邊界
- 團隊採用 Feature Team 模式，一組人完整負責一條功能線
- 功能之間差異大、共用邏輯少，強行共用反而增加耦合的場景（例如電商的「下單」跟「退貨」邏輯差異很大）
- 需要頻繁新增/替換功能，且希望新功能不影響既有功能穩定性的系統

---

## 業界知名人士的看法

> **Jimmy Bogard**（MediatR / AutoMapper 作者，VSA 概念推廣者）
> "Group code by feature, not by technical layer... Instead, organize your code by grouping all of the concerns around a single feature together in a slice."
> 出處：*Vertical Slice Architecture*（jimmybogard.com，2016）
>
> 同一篇文章中他也提醒：VSA 不代表切片內部不能有分層，而是**不要強迫所有切片共用同一套水平分層**——每個切片依自己需求決定要多複雜。

> **Robert C. Martin（Uncle Bob）**——Clean Architecture 提出者
> 他的核心主張是「依賴應該指向業務規則（Entities/Use Case），而不是指向資料庫或 UI 框架」，這跟 VSA 的「以功能為中心」精神有相通之處，但 Clean Architecture 更強調**分層之間的依賴方向**，VSA 更強調**功能之間的獨立性**。兩者常被拿來比較，但解決的其實是不完全相同的問題（依賴方向 vs 程式碼組織方式）。

> **Derek Comartin**（CodeOpinion，長期撰寫 VSA / CQRS / 事件驅動架構內容的部落客）
> 他多次強調 VSA 常見的誤解：「VSA 不是一種『架構模式』，而是一種『程式碼組織策略』，可以跟任何架構（Clean Architecture、Hexagonal 等）並存。」也就是說 VSA 跟 Clean Architecture 並非互斥的二選一。

> **Milan Jovanović**（.NET 內容創作者，大量產出 VSA vs Clean Architecture 比較內容）
> 他常見的立場是：Clean Architecture 在**大型、長生命週期、多團隊**的系統中優勢明顯（強制依賴方向、易於測試），但對**中小型專案**容易變成過度設計；VSA 則更貼近「Simple, but not too simple」的實務折衷。他也多次強調，選架構要看團隊規模跟專案複雜度，沒有放諸四海皆準的答案。

> **社群普遍共識**（多篇 InfoQ / .NET Conf 分享內容）
> VSA 討論度上升是事實，但實際企業採用仍以傳統分層與 Clean Architecture 為主流，VSA 目前更常見於：新創、API 為主的微服務、或是願意投入前期慣例建立成本的團隊。

---

## 常見誤解 / FAQ

**Q: VSA 就是不用分層了嗎？**
不是。VSA 反對的是「強迫所有功能共用同一套水平分層」，切片內部一樣可以有 Command/Handler/Validator 這種小分層，只是這個分層是「服務於這一個功能」，不是「服務於全專案的統一規範」。

**Q: VSA 一定要搭配 MediatR/CQRS 嗎？**
不用。這是最常見的搭配（因為 `IRequestHandler` 很適合表達「一個切片一個處理者」），但你也可以不用 MediatR，直接讓 Minimal API 端點呼叫一個切片專屬的 service 方法。重點是資料夾組織方式，不是特定套件。

**Q: 傳統三層架構是不是過時了？**
不是。傳統分層依然是主流，特別是企業內部系統跟中小型 CRUD 應用。VSA 解決的是特定情境下的問題（功能間耦合、CQRS 需求、Feature Team 組織），不是「更新的就一定更好」。

**Q: 可以兩種混合使用嗎？**
可以，但要謹慎。常見的穩健做法是「整個專案統一一種慣例」，如果真要混用，通常是「新模組全部用一種方式建立，並在文件中明確定義規則」，避免同一個專案裡出現無法預測的兩套邏輯，增加維護與 onboarding 成本。

---

## 中間路線：VSA-lite（Feature Folder，不上 CQRS/MediatR）

如果團隊想要 VSA 的「內聚」好處，又不想引入 MediatR / CQRS 的額外複雜度，可以採用更輕量的「Feature Folder」做法：

```
Features/
  Orders/
    OrderService.cs        // 這個功能所有的業務邏輯都在這一個 Service
    OrderDto.cs
    OrderEndpoints.cs       // 或者是 Controller/Razor Page
Shared/
  AppDbContext.cs
  Entities/
```

這種做法保留「按功能分資料夾」的內聚性，但不強制 Command/Query/Handler 的儀式，適合中小型團隊、CRUD 為主但仍想避免「改一個功能跳 4 個資料夾」的情境。可以理解為「VSA 的資料夾哲學 + 傳統三層的實作習慣」的折衷。

---

## Blazor Server 的特殊考量

VSA 的論述絕大多數是針對 **Web API**（HTTP Request → Handler → Response 的模型）。Blazor Server 的進入點是**元件生命週期**（`OnInitializedAsync` 等），不是 HTTP request/response，因此：

- 嚴格意義的 CQRS + MediatR 式 VSA，在 Blazor 元件上沒有天然對應的「Request 進來」的邊界
- 較適合套用的其實是上面提到的 **Feature Folder（VSA-lite）**：把同一個頁面（`.razor`）、對應的 Service、DTO 放在同一個資料夾，但不強求 Command/Handler 的形式
- 共用元件（Layout、共用下拉選單等）、跨切面關注點（Auth、DbContext、Logging）仍應集中管理，不屬於任何單一切片

因此在 Blazor Server 專案上討論「要不要上 VSA」時，實務上通常是在討論「要不要改成 Feature Folder」，而不是完整的 CQRS 式 VSA。

---

## 決策檢查表

在考慮是否要導入 VSA（或其輕量版）之前，可以先自問：

- [ ] 我們是否常常「改一個功能要跳 3～4 個資料夾找檔案」，而且這造成實際的開發困擾（不是偶爾抱怨一下）？
- [ ] 團隊是否以 Feature Team 方式運作（一組人完整負責一條功能線），而不是按技術職能分工？
- [ ] 系統的讀寫邏輯（Query/Command）差異是否明顯，適合分開建模？
- [ ] 專案是否有計畫拆分成微服務，需要先在單體內建立清楚的功能邊界？
- [ ] 團隊是否有意願、有時間建立並維護新的慣例（文件、code review 規範），而不是悄悄引入沒人講清楚的新模式？

**如果以上大多數答案是「否」**，維持現有架構（或漸進採用 Feature Folder 輕量版）通常是更務實的選擇；跟風換架構本身不是理由。

---

## 延伸閱讀

- Jimmy Bogard, *Vertical Slice Architecture*（jimmybogard.com，2016 年原文，VSA 概念起源）
- Jimmy Bogard, MediatR 專案文件與範例（github.com/jbogard/MediatR）
- Derek Comartin (CodeOpinion), *Vertical Slice Architecture* 系列文章與影片
- Milan Jovanović, *Vertical Slice Architecture* 與 *Clean Architecture* 比較系列文章
- Jason Taylor, Clean Architecture 官方範本（github.com/jasontaylordev/CleanArchitecture）
- Robert C. Martin, *Clean Architecture: A Craftsman's Guide to Software Structure and Design*（書籍，2017）
