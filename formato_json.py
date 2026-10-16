from pydantic import BaseModel, Field 
from typing import Optional

class ItemNotaFiscal(BaseModel):
    """Representa um produto de uma nota fiscal brasileira, especificamente no estado do Ceará.
    
    A entrada é a descrição o nome e (pode vir sem marca) a marca de um produto, abreviado, em caixa
    alta e sem acentuação."""
    
    alimenticio : bool = Field(
        description=(
            "true se o item for destinado ao consumo humano como alimento, "
            "bebida, tempero ou ingrediente culinário. "
            "false para limpeza, higiene, farmácia, eletrônicos, vestuário, "
            "papelaria, ração animal e demais categorias."            
        )
    )
    
    produto : Optional[str] = Field(
        default=None,
        description=(
            "Nome do produto por extenso, com abreviações expandidas e "
            "acentuação correta, em Capitalização de Título. "
            "Não inclua a marca, o volume, o peso nem a quantidade. "
            "Use null se alimenticio for false."            
        )
    )
    
    marca : Optional[str] = Field(
        default=None,
        description=(
            "Marca do fabricante, grafada como a empresa a escreve "
            "(ex.: 'Nestlé', não 'NESTLE' nem 'Nestle S.A.'). "
            "Use null se alimenticio for false OU se nenhuma marca for "
            "identificável no texto."            
        )
    )

