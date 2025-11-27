import streamlit as st
import pulp

def solve_lp(A, b, obj, signal, tipo, n, m, name="PPL"):
    """Monta e resolve um PPL com dados fornecidos."""
    x = [pulp.LpVariable(f"x{i+1}_{name}", lowBound=0) for i in range(n)]

    prob = pulp.LpProblem(
        name,
        pulp.LpMaximize if tipo == "Maximizar" else pulp.LpMinimize
    )

    # Função objetivo
    prob += sum(obj[i] * x[i] for i in range(n))

    # Restrições
    for j in range(m):
        expr = sum(A[j][i] * x[i] for i in range(n))
        if signal[j] == "<=":
            prob += expr <= b[j]
        elif signal[j] == ">=":
            prob += expr >= b[j]
        else:
            prob += expr == b[j]

    prob.solve()
    return prob, x


def intervalo_preco_sombra(idx, A, b, obj, signal, tipo,
                           passo=1.0, max_passos=20, tol=1e-4):
    """
    Estima, numericamente, o intervalo em que o preço-sombra da
    restrição idx permanece aproximadamente constante.
    Retorna (b_down, b_up, y0).
    """
    n, m = len(obj), len(b)

    # Problema base
    prob_base, _ = solve_lp(A, b, obj, signal, tipo, n, m, name="base")
    status_base = pulp.LpStatus[prob_base.status]
    if status_base != "Optimal":
        return None, None, None

    y0 = list(prob_base.constraints.values())[idx].pi

    # Variação para cima
    b_up = b[idx]
    for _ in range(max_passos):
        b_test = b.copy()
        b_test[idx] = b_up + passo
        prob_up, _ = solve_lp(A, b_test, obj, signal, tipo, n, m, name=f"up_{idx}")
        if pulp.LpStatus[prob_up.status] != "Optimal":
            break
        y_up = list(prob_up.constraints.values())[idx].pi
        if abs(y_up - y0) > tol:
            break
        b_up += passo

    # Variação para baixo
    b_down = b[idx]
    for _ in range(max_passos):
        b_test = b.copy()
        b_test[idx] = b_down - passo
        prob_down, _ = solve_lp(A, b_test, obj, signal, tipo, n, m, name=f"down_{idx}")
        if pulp.LpStatus[prob_down.status] != "Optimal":
            break
        y_down = list(prob_down.constraints.values())[idx].pi
        if abs(y_down - y0) > tol:
            break
        b_down -= passo

    return b_down, b_up, y0


# Interface

st.title("Simplex Tableau")
st.write(
    "Aplicação para resolver PPL com 2, 3 ou 4 variáveis, "
    "calcular preços-sombra e analisar alterações nos limites das restrições."
)

with st.sidebar:
    st.header("Configurações do problema")
    tipo = st.selectbox("Tipo do problema", ["Maximizar", "Minimizar"])
    n = st.selectbox("Número de variáveis", [2, 3, 4])
    m = st.number_input("Quantas restrições?", min_value=1, max_value=10,
                        value=2, step=1)

st.subheader("Função Objetivo")
obj = [st.number_input(f"Coeficiente de x{i+1}", value=0.0)
       for i in range(n)]

st.subheader("Restrições")
A, b, delta, signal = [], [], [], []

for j in range(m):
    st.markdown(f"**Restrição {j+1}**")
    A.append([st.number_input(f"Coeficiente de x{i+1} (R{j+1})", value=0.0,
                              key=f"a_{j}_{i}")
              for i in range(n)])

    signal.append(
        st.selectbox(
            f"Tipo da restrição {j+1}",
            ["<=", ">=", "="],
            key=f"sinal_{j}"
        )
    )

    b.append(st.number_input(f"LD{j+1}", value=0.0, key=f"b_{j}"))

    delta.append(
        st.number_input(
            f"Variação desejada em LD{j+1}",
            value=0.0,
            key=f"delta_{j}"
        )
    )

if st.button("Resolver"):
    # Problema original 
    prob, x = solve_lp(A, b, obj, signal, tipo, n, m, name="PPL")

    status = pulp.LpStatus[prob.status]
    st.subheader("Resultado")
    st.write("Status do problema:", status)

    if status != "Optimal":
        st.error("Problema não possui solução ótima (pode ser inviável ou ilimitado).")
        st.stop()

    # Solução ótima 
    solucao = {f"x{i+1}": float(v.value()) for i, v in enumerate(x)}
    st.write(solucao)
    st.write("Valor da Função Objetivo:", float(pulp.value(prob.objective)))

    # PS
    st.subheader("Preços-Sombra (Dual)")
    constraints = list(prob.constraints.values())
    precos = {f"Restrição {j+1}": float(constraints[j].pi) for j in range(m)}
    st.write(precos)

    # Problema com alterações nos LDs 
    new_b = [b[j] + delta[j] for j in range(m)]

    st.subheader("Análise com alterações")
    st.write("Novos LDs:", new_b)

    prob2, x2 = solve_lp(A, new_b, obj, signal, tipo, n, m, name="NovoPPL")
    status2 = pulp.LpStatus[prob2.status]
    st.write("Status após alterações:", status2)

    if status2 != "Optimal":
        st.error("Alterações inviáveis: o problema modificado não possui solução ótima.")
    else:
        st.success("Alterações viáveis.")
        nova_solucao = {f"x{i+1}": float(v.value()) for i, v in enumerate(x2)}
        st.write("Novo ponto ótimo de operação:")
        st.write(nova_solucao)
        st.write("Novo valor da função objetivo:",
                 float(pulp.value(prob2.objective)))

    # Intervalo de validade dos PS
    st.subheader("Limites aproximados de validade dos preços-sombra")
    st.write(
        "Para cada restrição, é estimado um intervalo de valores de LD "
        "em que o preço-sombra permanece aproximadamente constante."
    )

    for j in range(m):
        b_down, b_up, yj = intervalo_preco_sombra(j, A, b, obj, signal, tipo)
        if b_down is None:
            st.write(f"Restrição {j+1}: não foi possível estimar o intervalo.")
        else:
            st.write(
                {
                    f"Restrição {j+1}": {
                        "preço_sombra": float(yj),
                        "LD_mínimo": float(b_down),
                        "LD_máximo": float(b_up),
                    }
                }
            )
