# Importa a função "run" a partir do ficheiro ui/main_window.py
# Esta função é responsável por:
# - criar a janela principal da aplicação
# - inicializar a interface gráfica (UI)
# - arrancar o loop principal do programa (event loop)
from ui.main_window import run


# Esta verificação garante que o código abaixo
# só é executado quando este ficheiro é executado diretamente,
# e NÃO quando é importado por outro ficheiro Python.
if __name__ == "__main__":

    # Chama a função run()
    #
    # Na prática, isto:
    # - cria a aplicação OmniFlow Terminal
    # - abre a janela principal
    # - mantém a app a correr até o utilizador fechar
    #
    # Este é o verdadeiro "START" da aplicação.
    run()
