# Navegação da interface web

A navegação principal do console é configurada no arquivo [`src/config/navigation.ts`](../../src/config/navigation.ts). Cada item do array `navigationItems` representa um botão do header e aceita a seguinte estrutura:

```ts
interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIconComponent;
  match?: "exact" | "startsWith";
  children?: NavigationItem[];
}
```

## Regras de configuração

- Use `match: "startsWith"` quando a rota possuir subpáginas que devem manter o item pai ativo (por exemplo, `/contacts` cobre `/contacts/import`).
- Itens com `children` são renderizados como menus suspensos no desktop e como uma lista hierárquica dentro do drawer mobile. Inclua o próprio item pai dentro de `children` se quiser preservar o atalho direto (ex.: `Campanhas` para `/messages`).
- Adicione ícones da biblioteca `lucide-react`. O mesmo ícone pode ser reutilizado em pais e filhos.
- Sempre forneça um `href` existente nas rotas declaradas em `src/App.tsx` para evitar links quebrados.

## Como adicionar subitens

1. Abra [`src/config/navigation.ts`](../../src/config/navigation.ts).
2. Localize o item desejado e acrescente um novo objeto no array `children` com `label`, `href` e `icon`.
3. Caso a nova rota possua sub-rotas adicionais, utilize `match: "startsWith"` no próprio subitem.
4. Opcional: atualize testes ou mocks que dependam da lista de navegação.
5. Execute `npm run lint` e os testes relevantes para garantir que não haja regressões.

As mudanças são refletidas automaticamente tanto no header quanto no menu mobile.
